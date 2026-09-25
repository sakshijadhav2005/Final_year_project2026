"""add event fields and recording event_id

Revision ID: 0003_add_event_fields
Revises: 0002_add_events_table
Create Date: 2026-09-24 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_add_event_fields'
down_revision = '0003_add_event_id_to_jobs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to events table
    op.add_column('events', sa.Column('location', sa.String(length=255), nullable=True))
    op.add_column('events', sa.Column('banner_image', sa.String(length=1024), nullable=True))
    op.add_column('events', sa.Column('description', sa.Text(), nullable=True))
    
    # Add event_id to recordings table
    op.add_column('recordings', sa.Column('event_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_recordings_event_id'), 'recordings', ['event_id'], unique=False)
    op.create_foreign_key(None, 'recordings', 'events', ['event_id'], ['id'])


def downgrade() -> None:
    # Remove event_id from recordings table
    op.drop_constraint(None, 'recordings', type_='foreignkey')
    op.drop_index(op.f('ix_recordings_event_id'), table_name='recordings')
    op.drop_column('recordings', 'event_id')
    
    # Remove new columns from events table
    op.drop_column('events', 'description')
    op.drop_column('events', 'banner_image')
    op.drop_column('events', 'location')
