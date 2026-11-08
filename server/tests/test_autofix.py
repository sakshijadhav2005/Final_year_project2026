"""Error-repair agent: capture, risk scan, the worktree loop and the approval API.

The agent itself is faked and git runs in a throwaway repository, so these tests are free
and never touch the real repository or GitHub."""

import asyncio
import subprocess
import uuid
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.autofix import AutoFixIssue
from app.services.autofix import agent
from app.services.autofix.capture import (
    fingerprint,
    is_external,
    js_location,
    python_location,
    record_error,
    record_exception,
    redact,
)
from app.services.autofix.review import scan_diff
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture(autouse=True, scope="module")
def _tables():
    from app.db.session import init_db

    asyncio.run(init_db())


@pytest.fixture
def dev_mode(monkeypatch):
    """The agent only runs in development; tests run in "test". The background worker
    stays off: it would pick up errors other tests left in the shared database."""
    monkeypatch.setattr(get_settings(), "eventai_env", "development")

    async def no_worker() -> None:
        return None

    monkeypatch.setattr(agent, "run_worker", no_worker)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tiny project with a bug, a bare 'GitHub' remote, and the agent pointed at it."""
    root = tmp_path / "repo"
    (root / "server" / "app").mkdir(parents=True)
    (root / "server" / "app" / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "dev@example.com")
    _git(root, "config", "user.name", "Dev")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    _git(root, "remote", "add", "origin", str(remote))

    s = get_settings()
    monkeypatch.setattr(agent, "REPO", root)
    monkeypatch.setattr(s, "autofix_worktree_root", str(tmp_path / "worktrees"))
    monkeypatch.setattr(s, "autofix_llm_review", False)
    monkeypatch.setattr(agent, "gh_cmd", lambda: None)
    return root, remote


def _boom() -> None:
    {}["missing"]


# ---------------------------------------------------------------- capture


def test_location_and_fingerprint_group_repeats() -> None:
    try:
        _boom()
    except KeyError as exc:
        where = python_location(exc)
    assert where is None or where.endswith(":_boom")  # tests are outside server/app
    a = fingerprint("KeyError", "server/app/x.py:f", "'missing' 123")
    assert a == fingerprint("KeyError", "server/app/x.py:f", "'other' 456")
    assert a != fingerprint("KeyError", "server/app/y.py:f", "'missing'")
    # No location: ids and numbers are ignored so repeats still group.
    assert fingerprint("E", None, "job 1234 failed") == fingerprint("E", None, "job 98765 failed")


def test_frontend_stack_points_at_our_source() -> None:
    stack = (
        "TypeError: Cannot read properties of undefined (reading 'map')\n"
        "    at JobList (http://localhost:5173/src/components/dashboard/JobList.tsx?t=17:42:18)\n"
        "    at renderWithHooks (http://localhost:5173/node_modules/.vite/deps/react-dom.js:1:2)"
    )
    assert js_location(stack) == "client/src/components/dashboard/JobList.tsx:JobList"


def test_secrets_are_removed(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", "AIzaSyTESTKEY1234567890")
    text = redact(
        "key=AIzaSyTESTKEY1234567890 Authorization: Bearer abc.def.ghijklmnop "
        "user ana@example.com /media?token=eyJhbGciOi.eyJzdWIiOiIx.c2lnbmF0dXJl "
        "postgresql+asyncpg://eventai:pw@db:5432/x"
    )
    assert "AIzaSy" not in text and "abc.def" not in text
    assert "ana@example.com" not in text and "eyJ" not in text and ":pw@" not in text


def test_service_problems_are_not_sent_to_the_agent() -> None:
    assert is_external("ResourceExhausted", "429 quota exceeded")
    assert is_external("RuntimeError", "Could not connect to server: Connection refused")
    assert not is_external("KeyError", "'summary'")


def test_record_counts_repeats_and_marks_external(dev_mode) -> None:
    async def scenario():
        tag = uuid.uuid4().hex[:6]
        for _ in range(3):
            try:
                {}[tag]
            except KeyError as exc:
                await record_exception(exc, source="api", context={"path": "/x"})
        await record_error(source="pipeline", error_type="ResourceExhausted", message=f"429 quota {tag}")
        async with SessionLocal() as db:
            rows = (await db.execute(select(AutoFixIssue))).scalars().all()
        return tag, rows

    tag, rows = asyncio.run(scenario())
    mine = [r for r in rows if tag in r.message]
    assert {r.status for r in mine} == {"new", "external"}
    assert next(r for r in mine if r.status == "new").occurrences == 3


def test_nothing_is_recorded_outside_development() -> None:
    async def scenario():
        await record_error(source="api", error_type="X", message="only-in-dev-check")
        async with SessionLocal() as db:
            return (await db.execute(
                select(AutoFixIssue).where(AutoFixIssue.message == "only-in-dev-check")
            )).scalar_one_or_none()

    assert asyncio.run(scenario()) is None


# ---------------------------------------------------------------- risk scan


def test_scan_flags_risky_changes() -> None:
    safe = (
        "diff --git a/server/app/calc.py b/server/app/calc.py\n--- a/server/app/calc.py\n"
        "+++ b/server/app/calc.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a - b\n+    return a + b\n"
    )
    assert scan_diff(safe)["risk"] == "low"

    auth = (
        "--- a/server/app/api/v1/jobs.py\n+++ b/server/app/api/v1/jobs.py\n@@ -10,3 +10,3 @@\n"
        "-    user: Annotated[User, Depends(get_current_user)],\n+    user=None,\n"
    )
    result = scan_diff(auth)
    assert result["risk"] == "high"
    assert any("login" in f["finding"] for f in result["findings"])

    env = "--- /dev/null\n+++ b/.env\n@@ -0,0 +1 @@\n+GEMINI_API_KEY=x\n"
    assert scan_diff(env)["blocked"] is True

    sql = "--- a/server/app/x.py\n+++ b/server/app/x.py\n@@ -1 +1 @@\n+db.execute(text(f\"SELECT {q}\"))\n"
    assert scan_diff(sql)["findings"][0]["line"] == 1


# ---------------------------------------------------------------- Portkey gateway


def _headers(env: dict) -> dict:
    return dict(line.split(": ", 1) for line in env["ANTHROPIC_CUSTOM_HEADERS"].split("\n"))


def test_agent_goes_through_portkey_with_a_trace_per_error(monkeypatch) -> None:
    s = get_settings()
    for key, value in {"autofix_llm_gateway": "portkey", "portkey_api_key": "pk-test",
                       "autofix_portkey_config": "pc-autofix", "autofix_portkey_virtual_key": "",
                       "anthropic_api_key": "sk-ant-real"}.items():
        monkeypatch.setattr(s, key, value)
    env = agent.gateway_env("abc123", "fix-round-1")
    assert env["ANTHROPIC_BASE_URL"] == "https://api.portkey.ai"
    h = _headers(env)
    assert h["x-portkey-api-key"] == "pk-test" and h["x-portkey-config"] == "pc-autofix"
    assert h["x-portkey-trace-id"] == "autofix-abc123"
    assert '"stage": "fix-round-1"' in h["x-portkey-metadata"]
    assert "x-portkey-provider" not in h
    # The config holds the provider credentials, so the real key is not sent.
    assert env["ANTHROPIC_API_KEY"] == "portkey-managed"
    # An inherited login token must never reach the gateway.
    assert env["ANTHROPIC_AUTH_TOKEN"] == ""
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "oauth-of-the-developer")
    assert "ANTHROPIC_AUTH_TOKEN" not in agent._env(env)


def test_portkey_routes_virtual_key_and_provider(monkeypatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "autofix_llm_gateway", "portkey")
    monkeypatch.setattr(s, "portkey_api_key", "pk-test")
    monkeypatch.setattr(s, "autofix_portkey_config", "")
    monkeypatch.setattr(s, "autofix_portkey_virtual_key", "vk-anthropic")
    monkeypatch.setattr(s, "anthropic_api_key", "")
    assert _headers(agent.gateway_env("f", "review"))["x-portkey-virtual-key"] == "vk-anthropic"

    monkeypatch.setattr(s, "autofix_portkey_virtual_key", "")
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-real")
    env = agent.gateway_env("f", "review")
    assert _headers(env)["x-portkey-provider"] == "anthropic"
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-real"  # Portkey forwards it to Anthropic


def test_unconfigured_portkey_blocks_the_agent(monkeypatch, tmp_path) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "autofix_llm_gateway", "portkey")
    monkeypatch.setattr(s, "portkey_api_key", "")
    status = agent.gateway_status()
    assert status["ready"] is False and "PORTKEY_API_KEY" in status["detail"]
    monkeypatch.setattr(agent, "find_agent_cmd", lambda: "claude")
    reply = asyncio.run(agent.call_agent("x", tmp_path, session_id="s", resume=False))
    assert "PORTKEY_API_KEY" in reply["error"]  # never silently falls back to a direct call

    monkeypatch.setattr(s, "portkey_api_key", "pk")
    for key in ("autofix_portkey_config", "autofix_portkey_virtual_key", "anthropic_api_key"):
        monkeypatch.setattr(s, key, "")
    assert agent.gateway_status()["ready"] is False

    monkeypatch.setattr(s, "autofix_llm_gateway", "direct")
    assert agent.gateway_env("f", "fix") == {}


# ---------------------------------------------------------------- the loop


async def _new_issue() -> uuid.UUID:
    async with SessionLocal() as db:
        from datetime import UTC, datetime

        issue = AutoFixIssue(
            fingerprint=uuid.uuid4().hex[:16], source="api", error_type="AssertionError",
            message="add(2, 2) returned 0", location="server/app/calc.py:add",
            last_seen=datetime.now(UTC),
        )
        db.add(issue)
        await db.commit()
        return issue.id


def _fake_agent(fix: str):
    calls: list[dict] = []

    async def call_agent(prompt, cwd, *, session_id, resume, read_only=False, fingerprint="", stage=""):
        calls.append({"prompt": prompt, "resume": resume, "session_id": session_id, "stage": stage})
        (Path(cwd) / "server" / "app" / "calc.py").write_text(fix)
        return {"text": '```json\n{"fixed": true, "title": "Return the sum in add()", "risk": "low",'
                        ' "root_cause": "add() subtracted"}\n```', "cost": 0.1, "error": None}

    return call_agent, calls


async def _load(issue_id) -> AutoFixIssue:
    async with SessionLocal() as db:
        return (await db.execute(select(AutoFixIssue).where(AutoFixIssue.id == issue_id))).scalar_one()


def test_fix_retries_on_failing_checks_then_proposes(repo, monkeypatch) -> None:
    root, _ = repo
    fake, calls = _fake_agent("def add(a, b):\n    return a + b\n")
    monkeypatch.setattr(agent, "call_agent", fake)
    results = iter([
        {"passed": False, "backend": {"passed": False, "output": "1 failed: test_add"}},
        {"passed": True, "backend": {"passed": True, "output": "3 passed"}, "reproduced": True},
    ])

    async def checks(path, files):
        assert files == ["server/app/calc.py"]
        return next(results)

    monkeypatch.setattr(agent, "run_checks", checks)

    async def scenario():
        issue_id = await _new_issue()
        await agent.fix_issue(issue_id)
        return await _load(issue_id)

    issue = asyncio.run(scenario())
    assert issue.status == "proposed", issue.status_detail
    assert len(calls) == 2 and calls[1]["resume"] is True  # same session, given the failure
    assert "1 failed: test_add" in calls[1]["prompt"]
    assert "+    return a + b" in issue.diff
    assert issue.risk == "low" and issue.cost_usd == pytest.approx(0.2)
    # The developer's own checkout is untouched.
    assert "a - b" in (root / "server" / "app" / "calc.py").read_text()
    assert _git(root, "status", "--porcelain") == ""


def test_no_change_means_failed_and_cleaned_up(repo, monkeypatch) -> None:
    async def no_change(prompt, cwd, **_):
        return {"text": '```json\n{"fixed": false, "root_cause": "quota, not code"}\n```', "cost": 0.05, "error": None}

    monkeypatch.setattr(agent, "call_agent", no_change)

    async def scenario():
        issue_id = await _new_issue()
        await agent.fix_issue(issue_id)
        return await _load(issue_id)

    issue = asyncio.run(scenario())
    assert issue.status == "failed"
    assert "quota, not code" in issue.status_detail
    assert not agent._worktree(issue).exists()


def test_protected_file_change_is_never_proposed(repo, monkeypatch) -> None:
    async def touches_env(prompt, cwd, **_):
        (Path(cwd) / ".env").write_text("SECRET_KEY=x\n")
        return {"text": "{}", "cost": 0.0, "error": None}

    async def checks(path, files):
        return {"passed": True}

    monkeypatch.setattr(agent, "call_agent", touches_env)
    monkeypatch.setattr(agent, "run_checks", checks)

    async def scenario():
        issue_id = await _new_issue()
        await agent.fix_issue(issue_id)
        return await _load(issue_id)

    issue = asyncio.run(scenario())
    assert issue.status == "failed" and "protected" in issue.status_detail


# ---------------------------------------------------------------- approval API


def _admin(client: TestClient) -> dict:
    email = f"fixadmin_{uuid.uuid4().hex[:8]}@example.com"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "password123",
                                                      "role": "event_organizer"}).json()["access_token"]

    async def promote():
        from app.models.user import User

        async with SessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            user.role = "admin"
            await db.commit()

    client.portal.call(promote)
    return {"Authorization": f"Bearer {token}"}


def test_admin_approves_pushes_and_rejects(repo, monkeypatch) -> None:
    root, remote = repo
    fake, _ = _fake_agent("def add(a, b):\n    return a + b\n")
    monkeypatch.setattr(agent, "call_agent", fake)

    async def checks(path, files):
        return {"passed": True}

    monkeypatch.setattr(agent, "run_checks", checks)
    monkeypatch.setattr(get_settings(), "autofix_remote", str(remote))

    with TestClient(app) as client:
        headers = _admin(client)
        first = client.portal.call(_new_issue)
        second = client.portal.call(_new_issue)
        client.portal.call(agent.fix_issue, first)
        client.portal.call(agent.fix_issue, second)

        # Only admins see the queue.
        organizer = client.post("/api/v1/auth/register", json={
            "email": f"org_{uuid.uuid4().hex[:6]}@example.com", "password": "password123",
            "role": "event_organizer"}).json()["access_token"]
        assert client.get("/api/v1/autofix/issues",
                          headers={"Authorization": f"Bearer {organizer}"}).status_code == 403

        listed = client.get("/api/v1/autofix/issues?status_filter=proposed", headers=headers).json()
        assert {str(first), str(second)} <= {row["id"] for row in listed}
        detail = client.get(f"/api/v1/autofix/issues/{first}", headers=headers).json()
        assert detail["title"] == "Return the sum in add()" and "a + b" in detail["diff"]

        approved = client.post(f"/api/v1/autofix/issues/{first}/approve", headers=headers)
        assert approved.status_code == 200, approved.text
        body = approved.json()
        assert body["status"] == "approved" and body["decided_by"].startswith("fixadmin_")
        pushed = subprocess.run(["git", "--git-dir", str(remote), "log", "--format=%s", body["branch"]],
                                capture_output=True, text=True, check=True).stdout
        assert "fix(autofix): Return the sum in add()" in pushed
        assert not agent._worktree(_Fp(body["fingerprint"])).exists()
        # Approving twice is refused.
        assert client.post(f"/api/v1/autofix/issues/{first}/approve", headers=headers).status_code == 409

        rejected = client.post(f"/api/v1/autofix/issues/{second}/reject", headers=headers,
                               json={"reason": "Wrong place for the fix"}).json()
        assert rejected["status"] == "rejected" and rejected["feedback"] == "Wrong place for the fix"
        assert rejected["branch"] not in _git(root, "branch", "--list")

        assert client.post(f"/api/v1/autofix/issues/{second}/retry", headers=headers).json()["status"] == "new"


def test_revise_queues_feedback(repo, monkeypatch) -> None:
    fake, calls = _fake_agent("def add(a, b):\n    return a + b\n")
    monkeypatch.setattr(agent, "call_agent", fake)

    async def checks(path, files):
        return {"passed": True}

    monkeypatch.setattr(agent, "run_checks", checks)

    with TestClient(app) as client:
        headers = _admin(client)
        issue_id = client.portal.call(_new_issue)
        client.portal.call(agent.fix_issue, issue_id)
        res = client.post(f"/api/v1/autofix/issues/{issue_id}/revise", headers=headers,
                          json={"feedback": "Also handle None inputs"})
        assert res.json()["status"] == "revising"
        client.portal.call(agent.revise_issue, issue_id)
        assert "Also handle None inputs" in calls[-1]["prompt"] and calls[-1]["resume"] is True
        assert client.get(f"/api/v1/autofix/issues/{issue_id}", headers=headers).json()["status"] == "proposed"


def test_browser_errors_are_recorded_in_development(dev_mode) -> None:
    with TestClient(app) as client:
        res = client.post("/api/v1/autofix/client-errors", json={
            "name": "TypeError", "message": "x.map is not a function (browser-test)",
            "stack": "TypeError: x\n    at Feed (http://localhost:5173/src/pages/CommunityPage.tsx:10:5)",
            "page": "/community?token=secret",
        })
        assert res.status_code == 204

        async def find():
            async with SessionLocal() as db:
                return (await db.execute(select(AutoFixIssue).where(
                    AutoFixIssue.message == "x.map is not a function (browser-test)"))).scalar_one()

        row = client.portal.call(find)
        assert row.source == "frontend" and row.location == "client/src/pages/CommunityPage.tsx:Feed"
        assert row.context["page"] == "/community"


class _Fp:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint
