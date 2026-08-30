"""Initial migration

Revision ID: 04bfa8dab4e8
Revises: e76f2f948b6e
Create Date: 2026-08-04 12:02:07.615174

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04bfa8dab4e8'
down_revision: Union[str, Sequence[str], None] = 'e76f2f948b6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('landmark_description', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('customer_latitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('customer_longitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('pin_is_flagged', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('pin_feedback', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('pin_feedback')
        batch_op.drop_column('pin_is_flagged')
        batch_op.drop_column('customer_longitude')
        batch_op.drop_column('customer_latitude')
        batch_op.drop_column('landmark_description')