"""Remove API keys that SDK error messages embed in URLs (``...?key=XXXX``) from every
saved result and log, so the evaluation folder can be shared.

    python evaluation/scripts/redact.py
"""

import re

import harness

PATTERN = re.compile(r"(key=)[A-Za-z0-9._\-]{8,}")
changed = 0
for path in harness.RESULTS.rglob("*"):
    if path.is_file() and path.suffix in {".json", ".csv", ".log", ".txt", ".xml"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        new = PATTERN.sub(r"\1<redacted>", text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
print(f"redacted {changed} files")
