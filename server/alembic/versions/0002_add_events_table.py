"""add events table and update content pieces

Revision ID: 0002_add_events_table
Revises: 0001_placeholder
Create Date: 2026-09-23 00:58:00
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_events_table"
down_revision: Union[str, None] = "0001_placeholder"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("topic", sa.String(255), nullable=True),
        sa.Column("organizer_name", sa.String(255), nullable=True),
        sa.Column("type", sa.String(32), nullable=False, server_default="other"),
        sa.Column("organizer_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    with op.batch_alter_table("content_pieces") as batch_op:
        batch_op.add_column(sa.Column("event_id", sa.Uuid(as_uuid=True), sa.ForeignKey("events.id", ondelete="SET NULL"), nullable=True))
        batch_op.add_column(sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
        batch_op.add_column(sa.Column("author_name", sa.String(255), nullable=True))
        batch_op.alter_column("job_id", nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("content_pieces") as batch_op:
        batch_op.drop_column("author_name")
        batch_op.drop_column("user_id")
        batch_op.drop_column("event_id")
        batch_op.alter_column("job_id", nullable=False)

    op.drop_table("events")
