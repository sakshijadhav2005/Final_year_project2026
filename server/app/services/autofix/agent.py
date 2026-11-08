"""The repair loop: worktree -> Claude Code edits -> our checks -> feedback -> review -> proposal.

The agent can only read and edit files in its own git worktree (no shell, no web). We run
the tests ourselves and feed failures back. Nothing is committed or pushed until an admin
approves; rejecting deletes the worktree and the branch.
"""

import asyncio
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime, time
from pathlib import Path

import structlog
from sqlalchemy import func, select

from app.core.config import ROOT, get_settings
from app.db.session import SessionLocal
from app.models.autofix import AutoFixIssue
from app.services.autofix.capture import redact
from app.services.autofix.review import RISK_ORDER, changed_files, scan_diff

logger = structlog.get_logger("autofix")

REPO = ROOT
_AGENT_LOCK = asyncio.Lock()

SYSTEM_PROMPT = """You are the error-repair agent for EventAI: a FastAPI backend in server/ \
(Python, SQLAlchemy async, LangGraph pipeline, tests in server/tests with pytest) and a \
React + TypeScript client in client/src. An error happened while a developer was running the app. \
Find the root cause and make the smallest correct fix in this working copy.

Rules:
- For a backend bug, first add a regression test that fails because of this bug, in a new file \
server/tests/test_autofix_<short_name>.py, in the style of the existing tests. Then fix the code. \
For a frontend-only bug a test is optional.
- Fix the root cause with the smallest change. Do not refactor or reformat unrelated code.
- Never touch .env files, secrets, CI files or evaluation/results. Avoid auth, config, database \
and dependency files unless the bug is there.
- Never weaken a security or access check, never delete or loosen an existing test, never hide \
the error with a broad try/except.
- You cannot run commands. After your edits the system runs the tests and type checks and \
tells you the result.
- If the error is not caused by code in this repository (network, quota, credentials, input that \
is correctly rejected), make no changes and say so.

Always end your reply with one JSON object in a ```json block:
{"fixed": true or false, "title": "commit title, at most 70 characters", \
"root_cause": "why it happened, 1-3 sentences", "fix": "what you changed and why", \
"test": "path::test_name of the regression test, or empty", "risk": "low" | "medium" | "high", \
"notes": "anything the reviewer should check"}"""

REVIEW_PROMPT = """Review this proposed bug fix for EventAI as a strict senior reviewer. \
Check that it fixes the root cause of the error, does not break other behaviour, and does not \
weaken security (auth checks, input validation, secrets, injection, unsafe file or shell use). \
You may read files in this working copy. Do not edit anything.

End with one JSON object in a ```json block:
{"verdict": "approve" or "concerns", "risk": "low" | "medium" | "high", \
"notes": ["short point", "..."]}"""


# ---------------------------------------------------------------- helpers


def find_agent_cmd() -> str | None:
    """The Claude Code CLI: the configured path, then PATH, then the VS Code extension."""
    configured = get_settings().autofix_agent_cmd
    if configured:
        return configured if Path(configured).exists() or shutil.which(configured) else None
    found = shutil.which("claude")
    if found:
        return found
    home = Path.home()
    pattern = "anthropic.claude-code-*/resources/native-binary/claude*"
    candidates = [
        p for p in glob.glob(str(home / ".vscode" / "extensions" / pattern))
        if Path(p).name in ("claude", "claude.exe")
    ]
    if not candidates:
        return None
    version = lambda p: [int(x) for x in re.findall(r"claude-code-([\d.]+)", p)[0].split(".") if x]  # noqa: E731
    return max(candidates, key=version)


def gh_cmd() -> str | None:
    return shutil.which("gh")


def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    # A server started from inside a Claude Code terminal must still be able to run it.
    for key in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "utf-8"
    for key, value in (extra or {}).items():
        if value:
            env[key] = value
        else:
            env.pop(key, None)  # "" = make sure an inherited value is not used
    return env


class GatewayNotReady(RuntimeError):
    pass


def gateway_status() -> dict:
    """How the agent reaches the model, and whether that is configured."""
    s = get_settings()
    if s.autofix_llm_gateway == "direct":
        return {"gateway": "direct", "ready": True, "route": "Claude Code login (no gateway)"}
    if not s.portkey_api_key:
        return {"gateway": "portkey", "ready": False, "route": None,
                "detail": "Set PORTKEY_API_KEY to route the agent through Portkey"}
    if s.autofix_portkey_config:
        route = f"config {s.autofix_portkey_config}"
    elif s.autofix_portkey_virtual_key:
        route = "virtual key"
    elif s.anthropic_api_key:
        route = "provider anthropic (ANTHROPIC_API_KEY)"
    else:
        return {"gateway": "portkey", "ready": False, "route": None,
                "detail": "Portkey needs a way to reach Claude: set AUTOFIX_PORTKEY_CONFIG, "
                          "AUTOFIX_PORTKEY_VIRTUAL_KEY or ANTHROPIC_API_KEY"}
    return {"gateway": "portkey", "ready": True, "route": route}


def gateway_env(fingerprint: str, stage: str) -> dict[str, str]:
    """Environment that sends every Claude Code request through Portkey.

    Claude Code calls {ANTHROPIC_BASE_URL}/v1/messages and adds ANTHROPIC_CUSTOM_HEADERS
    (one "Name: value" per line). One trace id per error groups all fix rounds and the
    review in Portkey; metadata says which stage each call belongs to."""
    s = get_settings()
    if s.autofix_llm_gateway == "direct":
        return {}
    status = gateway_status()
    if not status["ready"]:
        raise GatewayNotReady(status["detail"])
    headers = {
        "x-portkey-api-key": s.portkey_api_key,
        "x-portkey-trace-id": f"autofix-{fingerprint}",
        "x-portkey-metadata": json.dumps(
            {"_user": "eventai-autofix", "feature": "autofix", "issue": fingerprint, "stage": stage}
        ),
    }
    if s.autofix_portkey_config:
        headers["x-portkey-config"] = s.autofix_portkey_config
    elif s.autofix_portkey_virtual_key:
        headers["x-portkey-virtual-key"] = s.autofix_portkey_virtual_key
    else:
        headers["x-portkey-provider"] = "anthropic"
    # The Anthropic key travels only when Portkey has to forward it. Otherwise a placeholder
    # keeps Claude Code from sending the developer's own login token to the gateway.
    forward_key = not (s.autofix_portkey_config or s.autofix_portkey_virtual_key)
    return {
        "ANTHROPIC_BASE_URL": s.autofix_portkey_base_url.rstrip("/"),
        "ANTHROPIC_CUSTOM_HEADERS": "\n".join(f"{k}: {v}" for k, v in headers.items()),
        "ANTHROPIC_API_KEY": s.anthropic_api_key if forward_key else "portkey-managed",
        "ANTHROPIC_AUTH_TOKEN": "",
    }


def _run_sync(
    args: list[str], cwd: Path, timeout: float, stdin: str | None = None, env: dict[str, str] | None = None,
) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args, cwd=str(cwd), input=stdin, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, env=_env(env),
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        return 124, f"{out}\n[timed out after {timeout:.0f}s]"
    except OSError as exc:
        return 127, str(exc)


async def _run(
    args: list[str], cwd: Path, timeout: float = 120, stdin: str | None = None, env: dict[str, str] | None = None,
) -> tuple[int, str]:
    # A thread, not asyncio subprocesses: those need the Proactor loop, which uvicorn
    # does not use on Windows when --reload is on.
    return await asyncio.to_thread(_run_sync, args, cwd, timeout, stdin, env)


async def _git(*args: str, cwd: Path | None = None, timeout: float = 120) -> tuple[int, str]:
    return await _run(["git", *args], cwd or REPO, timeout)


def _worktree(issue: AutoFixIssue) -> Path:
    return Path(get_settings().autofix_worktree_root) / issue.fingerprint


def _link_node_modules(worktree: Path) -> None:
    """Share the client's installed packages so the type check can run in the worktree."""
    src, dst = REPO / "client" / "node_modules", worktree / "client" / "node_modules"
    if not src.is_dir() or dst.exists() or not dst.parent.is_dir():
        return
    try:
        if sys.platform == "win32":
            import _winapi

            _winapi.CreateJunction(str(src), str(dst))
        else:
            os.symlink(src, dst, target_is_directory=True)
    except OSError as exc:
        logger.warning("autofix_node_modules_link_failed", error=str(exc))


def _unlink_node_modules(worktree: Path) -> None:
    # Remove the link itself first so nothing ever deletes the real node_modules through it.
    link = worktree / "client" / "node_modules"
    try:
        if link.is_symlink():
            link.unlink()
        elif link.exists() and sys.platform == "win32":
            # rmdir removes a junction without touching its target, and refuses a real,
            # non-empty folder, so this can never delete installed packages.
            os.rmdir(link)
    except OSError:
        pass


async def remove_worktree(issue: AutoFixIssue, delete_branch: bool) -> None:
    path = _worktree(issue)
    if path.exists():
        _unlink_node_modules(path)
        await _git("worktree", "remove", "--force", str(path))
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    await _git("worktree", "prune")
    if delete_branch and issue.branch:
        await _git("branch", "-D", issue.branch)


async def prepare_worktree(issue: AutoFixIssue) -> Path:
    code, head = await _git("rev-parse", "HEAD")
    if code != 0:
        raise RuntimeError(f"Not a git repository: {head.strip()}")
    _, base = await _git("rev-parse", "--abbrev-ref", "HEAD")
    issue.base_commit = head.strip()
    issue.base_branch = base.strip() if base.strip() != "HEAD" else "main"
    issue.branch = f"autofix/{issue.fingerprint[:10]}"
    await remove_worktree(issue, delete_branch=True)
    path = _worktree(issue)
    path.parent.mkdir(parents=True, exist_ok=True)
    code, out = await _git("worktree", "add", "-b", issue.branch, str(path), issue.base_commit)
    if code != 0:
        raise RuntimeError(f"git worktree add failed: {out.strip()[-500:]}")
    _link_node_modules(path)
    return path


async def worktree_diff(path: Path) -> str:
    await _git("add", "-A", cwd=path)  # include new files; staging in the worktree only
    _, diff = await _git("diff", "--cached", "--no-color", "HEAD", cwd=path)
    return diff


def _last_json(text: str) -> dict:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text or "", flags=re.DOTALL)
    candidates = blocks or re.findall(r"(\{[^{}]*\"[a-z_]+\"\s*:.*\})", text or "", flags=re.DOTALL)
    for raw in reversed(candidates):
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    return {}


# ---------------------------------------------------------------- the agent


async def call_agent(
    prompt: str, cwd: Path, *, session_id: str, resume: bool, read_only: bool = False,
    fingerprint: str = "", stage: str = "fix",
) -> dict:
    """One Claude Code turn, routed through the LLM gateway. Returns {"text", "cost", "error"}."""
    cmd = find_agent_cmd()
    if cmd is None:
        return {"text": "", "cost": 0.0, "error": "Claude Code CLI not found"}
    try:
        env = gateway_env(fingerprint or "unknown", stage)
    except GatewayNotReady as exc:
        return {"text": "", "cost": 0.0, "error": str(exc)}
    settings = get_settings()
    args = [
        cmd, "-p", "--output-format", "json",
        "--append-system-prompt", REVIEW_PROMPT if read_only else SYSTEM_PROMPT,
        "--max-budget-usd", str(settings.autofix_max_budget_usd),
        "--disallowedTools", "Bash", "WebFetch", "WebSearch", "NotebookEdit",
        "--permission-mode", "default" if read_only else "acceptEdits",
        "--allowedTools", *(("Read", "Glob", "Grep") if read_only else ("Read", "Edit", "Write", "Glob", "Grep")),
    ]
    args += ["--resume", session_id] if resume else ["--session-id", session_id]
    if settings.autofix_model:
        args += ["--model", settings.autofix_model]
    code, out = await _run(args, cwd, settings.autofix_timeout_seconds, stdin=prompt, env=env)
    try:
        payload = json.loads(out[out.find("{"):]) if "{" in out else {}
    except json.JSONDecodeError:
        payload = {}
    text = str(payload.get("result") or "")
    cost = float(payload.get("total_cost_usd") or 0.0)
    error = None
    if code != 0 or payload.get("is_error") or not payload:
        error = (text or out).strip()[-1500:] or f"exit code {code}"
    return {"text": text, "cost": cost, "error": error}


def _task_prompt(issue: AutoFixIssue) -> str:
    context = "\n".join(f"- {k}: {v}" for k, v in (issue.context or {}).items()) or "- none"
    return f"""An error was caught while the app was running.

Source: {issue.source} ({"backend API request" if issue.source == "api" else "background pipeline job" if issue.source == "pipeline" else "browser"})
Error: {issue.error_type}: {issue.message}
Where (deepest frame in our code): {issue.location or "unknown"}
Seen {issue.occurrences} time(s).
Context:
{context}

Stack trace (secrets removed):
```
{(issue.stack or "no stack trace")[-6000:]}
```

This working copy is the last commit ({(issue.base_commit or "")[:10]}) of branch \
{issue.base_branch}; the developer's uncommitted edits are not included. If the bug is not \
present here, say so and make no changes."""


# ---------------------------------------------------------------- checks


async def run_checks(path: Path, files: list[str]) -> dict:
    """Our own verification of the agent's change, independent of what it claims."""
    settings = get_settings()
    result: dict = {"backend": None, "frontend": None, "reproduced": None, "passed": True}
    backend = any(f.startswith("server/") for f in files)
    frontend = any(f.startswith("client/") for f in files)

    if backend:
        code, out = await _run(
            [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "--no-header"],
            path / "server", settings.autofix_check_timeout_seconds,
        )
        result["backend"] = {"passed": code == 0, "output": redact(out)[-4000:]}
        result["passed"] &= code == 0

        new_tests = [f for f in files if f.startswith("server/tests/") and f.endswith(".py")]
        source = [f for f in files if f.startswith("server/app/")]
        if code == 0 and new_tests and source:
            result["reproduced"] = await _reproduces(path, new_tests, source)

    if frontend:
        tsc = path / "client" / "node_modules" / "typescript" / "bin" / "tsc"
        if tsc.exists():
            code, out = await _run(
                ["node", str(tsc), "-b", "--noEmit"], path / "client", settings.autofix_check_timeout_seconds,
            )
            result["frontend"] = {"passed": code == 0, "output": redact(out)[-4000:]}
            result["passed"] &= code == 0
        else:
            result["frontend"] = {"passed": None, "output": "client/node_modules missing; type check skipped"}

    if not backend and not frontend:
        result["passed"] = False
        result["note"] = "The change touches no server/ or client/ files."
    return result


async def _reproduces(path: Path, tests: list[str], source: list[str]) -> bool | None:
    """Do the new tests fail on the original code? (Proves they test the bug.)"""
    code, _ = await _git("stash", "push", "--include-untracked", "--", *source, cwd=path)
    if code != 0:
        return None
    try:
        rel = [t.removeprefix("server/") for t in tests]
        test_code, _ = await _run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *rel],
            path / "server", get_settings().autofix_check_timeout_seconds,
        )
        return test_code != 0
    finally:
        await _git("stash", "pop", cwd=path)
        await _git("add", "-A", cwd=path)


def _check_feedback(checks: dict) -> str:
    parts = ["Your change did not pass the checks. Fix it, keeping the change small."]
    for name in ("backend", "frontend"):
        block = checks.get(name)
        if block and block.get("passed") is False:
            parts.append(f"{name} output:\n```\n{block['output'][-3500:]}\n```")
    if checks.get("note"):
        parts.append(checks["note"])
    parts.append("End with the same JSON object as before.")
    return "\n\n".join(parts)


# ---------------------------------------------------------------- the loop


async def _save(issue_id: uuid.UUID, **fields) -> AutoFixIssue:
    async with SessionLocal() as db:
        issue = (await db.execute(select(AutoFixIssue).where(AutoFixIssue.id == issue_id))).scalar_one()
        for key, value in fields.items():
            setattr(issue, key, value)
        await db.commit()
        await db.refresh(issue)
        return issue


async def _fix_rounds(issue: AutoFixIssue, path: Path, first_prompt: str, resume: bool) -> None:
    settings = get_settings()
    session_id = issue.session_id or str(uuid.uuid4())
    prompt, cost, report, checks, diff = first_prompt, issue.cost_usd or 0.0, {}, {}, ""

    for round_no in range(1, settings.autofix_max_rounds + 1):
        await _save(issue.id, status_detail=f"Agent working (round {round_no} of {settings.autofix_max_rounds})")
        reply = await call_agent(prompt, path, session_id=session_id, resume=resume or round_no > 1,
                                 fingerprint=issue.fingerprint, stage=f"fix-round-{round_no}")
        cost += reply["cost"]
        if reply["error"]:
            await _fail(issue, f"The agent stopped: {reply['error']}", cost=cost, session_id=session_id)
            return
        report = _last_json(reply["text"]) or {"fixed": None, "notes": reply["text"][-1500:]}
        diff = await worktree_diff(path)
        if not diff.strip():
            reason = report.get("root_cause") or report.get("notes") or "The agent made no changes."
            await _fail(issue, f"No fix proposed: {reason}", cost=cost, session_id=session_id, report=report)
            return
        await _save(issue.id, status_detail=f"Running tests (round {round_no})")
        checks = await run_checks(path, changed_files(diff))
        if checks["passed"]:
            break
        prompt = _check_feedback(checks)
    else:
        await _fail(issue, f"Checks still failing after {settings.autofix_max_rounds} rounds.",
                    cost=cost, session_id=session_id, report=report, checks=checks, diff=diff)
        return

    await _save(issue.id, status_detail="Reviewing the change")
    scan = scan_diff(diff)
    review: dict = {"scan": scan, "agent": None}
    if scan["blocked"]:
        await _fail(issue, "The change touched a protected file (.env, keys, CI or results).",
                    cost=cost, session_id=session_id, report=report, checks=checks, diff=diff, review=review)
        return
    if settings.autofix_llm_review:
        reply = await call_agent(
            f"The error:\n{issue.error_type}: {issue.message}\n\nThe proposed fix:\n```diff\n{diff[-30000:]}\n```",
            path, session_id=str(uuid.uuid4()), resume=False, read_only=True,
            fingerprint=issue.fingerprint, stage="review",
        )
        cost += reply["cost"]
        review["agent"] = _last_json(reply["text"]) or {"verdict": "unknown", "notes": [reply["error"] or reply["text"][-800:]]}

    risk = "low"
    for level in (scan["risk"], report.get("risk"), (review["agent"] or {}).get("risk")):
        if level in RISK_ORDER and RISK_ORDER[level] > RISK_ORDER[risk]:
            risk = level
    await _save(
        issue.id, status="proposed", status_detail="Waiting for your review", session_id=session_id,
        report=report, checks=checks, diff=diff[-200000:], review=review, risk=risk, cost_usd=round(cost, 4),
    )
    logger.info("autofix_proposed", fingerprint=issue.fingerprint, risk=risk, cost=round(cost, 4))


async def _fail(issue: AutoFixIssue, detail: str, **fields) -> None:
    if "cost" in fields:
        fields["cost_usd"] = round(fields.pop("cost"), 4)
    await _save(issue.id, status="failed", status_detail=detail[:2000], **fields)
    await remove_worktree(issue, delete_branch=True)
    logger.info("autofix_failed", fingerprint=issue.fingerprint, detail=detail[:200])


async def fix_issue(issue_id: uuid.UUID) -> None:
    async with _AGENT_LOCK:
        async with SessionLocal() as db:
            issue = (await db.execute(select(AutoFixIssue).where(AutoFixIssue.id == issue_id))).scalar_one()
            issue.status, issue.attempts = "fixing", issue.attempts + 1
            issue.fix_started_at = datetime.now(UTC)
            issue.status_detail, issue.session_id, issue.cost_usd = "Preparing a working copy", None, 0.0
            issue.report = issue.checks = issue.review = issue.diff = issue.risk = None
            try:
                path = await prepare_worktree(issue)
            except Exception as exc:
                issue.status, issue.status_detail = "failed", str(exc)[:2000]
                await db.commit()
                return
            await db.commit()
            await db.refresh(issue)
        try:
            await _fix_rounds(issue, path, _task_prompt(issue), resume=False)
        except Exception as exc:  # keep the worker alive whatever happens
            logger.exception("autofix_crashed", fingerprint=issue.fingerprint)
            await _fail(issue, f"The repair loop crashed: {exc}")


async def revise_issue(issue_id: uuid.UUID) -> None:
    """The admin asked for changes: continue the same agent session with their notes."""
    async with _AGENT_LOCK:
        async with SessionLocal() as db:
            issue = (await db.execute(select(AutoFixIssue).where(AutoFixIssue.id == issue_id))).scalar_one()
        path = _worktree(issue)
        if not path.exists():
            await _save(issue.id, status="new", status_detail="Working copy was gone; starting over")
            return
        prompt = (
            f"The reviewer asked for changes:\n\n{issue.feedback}\n\n"
            "Update the fix in this working copy. End with the same JSON object as before."
        )
        try:
            await _fix_rounds(issue, path, prompt, resume=bool(issue.session_id))
        except Exception as exc:
            logger.exception("autofix_crashed", fingerprint=issue.fingerprint)
            await _fail(issue, f"The repair loop crashed: {exc}")


# ---------------------------------------------------------------- decisions


def _github_compare_url(remote_url: str, base: str, branch: str) -> str | None:
    m = re.search(r"github\.com[:/](?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$", remote_url.strip())
    return f"https://github.com/{m.group('repo')}/compare/{base}...{branch}?expand=1" if m else None


async def approve(issue: AutoFixIssue, approver: str) -> AutoFixIssue:
    """Commit in the worktree, push the branch and open (or link) a pull request."""
    settings = get_settings()
    path = _worktree(issue)
    if not path.exists():
        raise RuntimeError("The working copy for this fix no longer exists. Retry the fix.")
    report = issue.report or {}
    title = (report.get("title") or f"Fix {issue.error_type} in {issue.location or issue.source}")[:70]
    body = "\n\n".join(filter(None, [
        f"Root cause: {report.get('root_cause')}" if report.get("root_cause") else None,
        f"Fix: {report.get('fix')}" if report.get("fix") else None,
        f"Error: {issue.error_type}: {issue.message[:300]}",
        f"Proposed by the EventAI repair agent, reviewed and approved in the admin console (risk: {issue.risk}).",
        "Co-Authored-By: Claude <noreply@anthropic.com>",
    ]))
    await _git("add", "-A", cwd=path)
    code, out = await _git("commit", "-m", f"fix(autofix): {title}", "-m", body, cwd=path)
    if code != 0 and "nothing to commit" not in out:
        raise RuntimeError(f"git commit failed: {out.strip()[-500:]}")
    code, out = await _git("push", "-u", settings.autofix_remote, issue.branch, cwd=path, timeout=180)
    if code != 0:
        raise RuntimeError(f"git push failed: {redact(out).strip()[-800:]}")

    pr_url = None
    if gh_cmd():
        code, out = await _run(
            [gh_cmd(), "pr", "create", "--draft", "--base", issue.base_branch, "--head", issue.branch,
             "--title", f"fix(autofix): {title}", "--body", body + "\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"],
            path, 120,
        )
        urls = re.findall(r"https://github\.com/\S+/pull/\d+", out)
        pr_url = urls[-1] if code == 0 and urls else None
    if pr_url is None:
        _, remote = await _git("remote", "get-url", settings.autofix_remote)
        pr_url = _github_compare_url(remote, issue.base_branch, issue.branch)

    await remove_worktree(issue, delete_branch=False)  # the branch stays: it is on GitHub now
    return await _save(
        issue.id, status="approved", pr_url=pr_url, decided_by=approver, decided_at=datetime.now(UTC),
        status_detail="Pushed. Open the pull request to merge it." if pr_url else "Pushed.",
    )


async def reject(issue: AutoFixIssue, approver: str, reason: str) -> AutoFixIssue:
    await remove_worktree(issue, delete_branch=True)
    return await _save(
        issue.id, status="rejected", feedback=reason or issue.feedback, decided_by=approver,
        decided_at=datetime.now(UTC), status_detail="Rejected; the working copy and branch were deleted.",
    )


# ---------------------------------------------------------------- worker


async def attempts_today() -> int:
    start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    async with SessionLocal() as db:
        return int((await db.execute(
            select(func.count()).select_from(AutoFixIssue).where(AutoFixIssue.fix_started_at >= start)
        )).scalar_one())


async def run_worker() -> None:
    """Started with the app in development: handles new errors and revision requests one by one."""
    settings = get_settings()
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(AutoFixIssue).where(AutoFixIssue.status.in_(("fixing", "revising")))
        )).scalars().all()
        for row in rows:  # interrupted by a restart: start them again
            row.status, row.status_detail = "new", "Restarted after the server restarted"
        await db.commit()

    while True:
        try:
            async with SessionLocal() as db:
                issue = (await db.execute(
                    select(AutoFixIssue)
                    .where(AutoFixIssue.status.in_(("new", "revising")))
                    .order_by(AutoFixIssue.status.desc(), AutoFixIssue.last_seen)  # revisions first
                    .limit(1)
                )).scalar_one_or_none()
            if issue is not None:
                if issue.status == "revising":
                    await revise_issue(issue.id)
                elif find_agent_cmd() is None:
                    await _save(issue.id, status_detail="Waiting: Claude Code CLI not found "
                                "(install it or set AUTOFIX_AGENT_CMD)")
                    await asyncio.sleep(max(settings.autofix_poll_seconds, 60))
                    continue
                elif not gateway_status()["ready"]:
                    await _save(issue.id, status_detail=f"Waiting: {gateway_status()['detail']}")
                    await asyncio.sleep(max(settings.autofix_poll_seconds, 60))
                    continue
                elif await attempts_today() >= settings.autofix_max_per_day:
                    await _save(issue.id, status_detail=f"Waiting: daily limit of "
                                f"{settings.autofix_max_per_day} fix attempts reached")
                    await asyncio.sleep(max(settings.autofix_poll_seconds, 300))
                    continue
                else:
                    await fix_issue(issue.id)
                continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("autofix_worker_error", error=str(exc))
        await asyncio.sleep(settings.autofix_poll_seconds)
