"""Test configuration.

Runs the suite in an isolated "test" environment so it never depends on the
developer's .env (e.g. a PostgreSQL server that is not running, or real API
keys that would make tests call paid services).

Set TEST_DATABASE_URL to run the same suite against PostgreSQL, e.g.
    TEST_DATABASE_URL=postgresql+asyncpg://eventai:eventai@localhost:5432/eventai_test
"""

import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="eventai-tests-"))

os.environ["EVENTAI_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", f"sqlite+aiosqlite:///{(_tmp / 'test.db').as_posix()}"
)
os.environ["MEDIA_ROOT"] = str(_tmp / "media")
os.environ["STORAGE_BACKEND"] = "local"
os.environ["USE_CELERY"] = "false"
os.environ["SENTRY_DSN"] = ""
# Force the offline fake providers so tests are deterministic and free.
for key in (
    "GEMINI_API_KEY",
    "VIDEODB_API_KEY",
    "PORTKEY_API_KEY",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_CLOUD_PROJECT",
):
    os.environ[key] = ""
os.environ["LLM_PROVIDER"] = "gemini"
