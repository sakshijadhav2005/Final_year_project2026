import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import TimestampMixin

# new -> fixing -> proposed -> approved | rejected
#                  proposed -> revising -> proposed   (admin asked for changes)
# new -> external   (not a code bug: quota, network, credentials)
# fixing -> failed  (the agent could not produce a passing fix; can be retried)
AUTOFIX_STATUSES = (
    "new", "external", "fixing", "proposed", "revising", "approved", "rejected", "failed",
)


class AutoFixIssue(TimestampMixin, Base):
    """One distinct error seen while the app runs, and the agent's proposed fix for it."""

    __tablename__ = "autofix_issues"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fingerprint: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # api | pipeline | frontend
    error_type: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)  # file:function
    stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurrences: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[str] = mapped_column(String(16), default="new", index=True, nullable=False)
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fix_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    branch: Mapped[str | None] = mapped_column(String(128), nullable=True)
    base_branch: Mapped[str | None] = mapped_column(String(128), nullable=True)
    base_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # root cause, fix, risk
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    checks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk: Mapped[str | None] = mapped_column(String(8), nullable=True)  # low | medium | high
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)  # admin's notes
    pr_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
