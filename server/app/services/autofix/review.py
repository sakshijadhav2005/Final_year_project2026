"""Deterministic risk scan of a proposed diff. Runs on every fix, with or without the
agent's own review, so a risky change is flagged even if the model misses it."""

import re

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

# The agent may never change these; a fix that does is not offered for approval.
FORBIDDEN = re.compile(
    r"(^|/)\.env($|\.)|\.pem$|\.key$|(^|/)\.git/|^evaluation/results/|(^|/)\.github/workflows/"
)
# Changes here are allowed but always need a careful look.
SENSITIVE = re.compile(
    r"server/app/(core/security|core/config|api/deps|api/v1/auth|services/auth|db/session|"
    r"middleware/|services/autofix/)|server/alembic/|requirements[^/]*\.txt$|package(-lock)?\.json$|"
    r"Dockerfile|docker-compose"
)

# (pattern on an added line, finding, risk)
_ADDED_LINE_RULES = [
    (re.compile(r"\b(eval|exec)\s*\("), "Runs dynamic code (eval/exec)", "high"),
    (re.compile(r"shell\s*=\s*True"), "Starts a shell command (shell=True)", "high"),
    (re.compile(r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false"), "Turns off TLS certificate checks", "high"),
    (re.compile(r"""(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*["'][^"'\s]{12,}["']"""),
     "Looks like a hard-coded secret", "high"),
    (re.compile(r"\b(sk-ant-|AIza|ghp_|github_pat_)[A-Za-z0-9_-]{10,}"), "Contains an API key", "high"),
    (re.compile(r"""(execute|text)\(\s*f["']"""), "SQL built with an f-string (injection risk)", "high"),
    (re.compile(r"dangerouslySetInnerHTML|\.innerHTML\s*="), "Writes raw HTML (XSS risk)", "medium"),
    (re.compile(r"allow_origins\s*=\s*\[\s*[\"']\*"), "Opens CORS to every site", "high"),
    (re.compile(r"except\s*(Exception)?\s*:\s*(pass)?\s*$"), "Swallows errors silently", "medium"),
    (re.compile(r"#\s*type:\s*ignore|@ts-ignore|eslint-disable|noqa"), "Silences a checker", "medium"),
    (re.compile(r"\b(rm\s+-rf|shutil\.rmtree|os\.remove|unlink\()"), "Deletes files", "medium"),
]
# (pattern on a removed line, finding, risk)
_REMOVED_LINE_RULES = [
    (re.compile(r"Depends\((get_current_user|require_admin|get_user_from_bearer_or_query)"),
     "Removes a login / admin check", "high"),
    (re.compile(r"_can_access|is_active|RequireAuth|RequireRole"), "Removes an access check", "high"),
    (re.compile(r"^\s*(def test_|it\(|test\()"), "Deletes a test", "high"),
    (re.compile(r"^\s*assert\s"), "Removes an assertion from a test", "medium"),
]


def _bump(current: str, new: str) -> str:
    return new if RISK_ORDER[new] > RISK_ORDER[current] else current


def changed_files(diff: str) -> list[str]:
    added = re.findall(r"^\+\+\+ b/(.+?)\s*$", diff, flags=re.MULTILINE)
    deleted = re.findall(r"^--- a/(.+?)\s*\n\+\+\+ /dev/null", diff, flags=re.MULTILINE)
    return sorted(set(added) | set(deleted))


def scan_diff(diff: str) -> dict:
    """Returns {"risk", "blocked", "findings": [{file, line, finding, risk}], "files"}."""
    files = changed_files(diff)
    findings: list[dict] = []
    risk, blocked = "low", False

    for path in files:
        if FORBIDDEN.search(path):
            findings.append({"file": path, "line": None, "finding": "Protected file changed", "risk": "high"})
            risk, blocked = "high", True
        elif SENSITIVE.search(path):
            findings.append({"file": path, "line": None, "finding": "Sensitive area (auth, config, "
                             "database, dependencies or this agent)", "risk": "high"})
            risk = "high"

    current, old_name, new_line = None, None, 0
    for raw in diff.splitlines():
        if raw.startswith("--- "):
            old_name = raw[6:].strip() if raw.startswith("--- a/") else None
            continue
        if raw.startswith("+++ "):
            current = raw[6:].strip() if raw.startswith("+++ b/") else old_name
            continue
        if raw.startswith(("diff --git", "index ", "new file", "deleted file", "similarity", "rename ")):
            continue
        hunk = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw)
        if hunk:
            new_line = int(hunk.group(1))
            continue
        if raw.startswith("+"):
            text = raw[1:]
            for pattern, finding, level in _ADDED_LINE_RULES:
                if pattern.search(text):
                    findings.append({"file": current, "line": new_line, "finding": finding, "risk": level})
                    risk = _bump(risk, level)
            new_line += 1
        elif raw.startswith("-"):
            text = raw[1:]
            for pattern, finding, level in _REMOVED_LINE_RULES:
                if pattern.search(text):
                    findings.append({"file": current, "line": None, "finding": finding, "risk": level})
                    risk = _bump(risk, level)
        else:
            new_line += 1

    big = sum(1 for line in diff.splitlines() if line[:1] in "+-" and line[:3] not in ("+++", "---"))
    if big > 300:
        findings.append({"file": None, "line": None, "finding": f"Large change ({big} lines)", "risk": "medium"})
        risk = _bump(risk, "medium")
    return {"risk": risk, "blocked": blocked, "findings": findings, "files": files}
