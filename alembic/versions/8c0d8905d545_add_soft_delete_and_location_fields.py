"""Add soft delete and location fields

Revision ID: 8c0d8905d545
Revises: 04bfa8dab4e8
Create Date: 2026-08-04 14:34:13.401139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c0d8905d545'
down_revision: Union[str, Sequence[str], None] = '04bfa8dab4e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('driver_shifts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=False))

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=False))
        batch_op.alter_column('created_at',
                   existing_type=sa.DATETIME(),
                   nullable=False)
        batch_op.drop_index('ix_orders_created_at')

    with op.batch_alter_table('support_tickets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=False))
        batch_op.alter_column('created_at',
                   existing_type=sa.DATETIME(),
                   nullable=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=False))

    with op.batch_alter_table('webhook_subscriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=False))
        batch_op.alter_column('created_at',
                   existing_type=sa.DATETIME(),
                   nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('webhook_subscriptions', schema=None) as batch_op:
        batch_op.alter_column('created_at',
                   existing_type=sa.DATETIME(),
                   nullable=True)
        batch_op.drop_column('updated_at')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    with op.batch_alter_table('support_tickets', schema=None) as batch_op:
        batch_op.alter_column('created_at',
                   existing_type=sa.DATETIME(),
                   nullable=True)
        batch_op.drop_column('updated_at')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('created_at',
                   existing_type=sa.DATETIME(),
                   nullable=True)
        batch_op.create_index('ix_orders_created_at', ['created_at'], unique=False)
        batch_op.drop_column('updated_at')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    with op.batch_alter_table('driver_shifts', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')