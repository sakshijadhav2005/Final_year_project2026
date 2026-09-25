"""add saved_content table

Revision ID: 0004_add_saved_content
Revises: 0003_add_event_fields
Create Date: 2026-09-25 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_add_saved_content'
down_revision = '0003_add_event_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'saved_content',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('content_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['content_id'], ['content_pieces.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_saved_content_user_id'), 'saved_content', ['user_id'], unique=False)
    op.create_index(op.f('ix_saved_content_content_id'), 'saved_content', ['content_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_saved_content_content_id'), table_name='saved_content')
    op.drop_index(op.f('ix_saved_content_user_id'), table_name='saved_content')
    op.drop_table('saved_content')
