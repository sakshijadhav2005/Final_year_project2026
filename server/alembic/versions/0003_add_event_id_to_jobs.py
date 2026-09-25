"""add event_id to jobs

Revision ID: 0003_add_event_id_to_jobs
Revises: 0002_add_events_table
Create Date: 2026-09-24 19:40:00
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_event_id_to_jobs"
down_revision: Union[str, None] = "0002_add_events_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "event_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("events.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.create_index("ix_jobs_event_id", ["event_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_event_id")
        batch_op.drop_column("event_id")
