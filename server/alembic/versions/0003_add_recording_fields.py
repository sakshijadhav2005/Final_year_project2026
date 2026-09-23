"""add event_id, sha256, storage_backend to recordings

Revision ID: 0003_add_recording_fields
Revises: 0002_add_events_table
Create Date: 2026-09-23 18:00:00
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_recording_fields"
down_revision: Union[str, None] = "0002_add_events_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("recordings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "event_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("events.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("storage_backend", sa.String(32), nullable=True, server_default="local")
        )
        batch_op.add_column(sa.Column("sha256", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("recordings") as batch_op:
        batch_op.drop_column("sha256")
        batch_op.drop_column("storage_backend")
        batch_op.drop_column("event_id")
