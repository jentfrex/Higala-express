"""add delivery_fee and product_id

Revision ID: 017eead37607
Revises: 96f603f00d6d
Create Date: 2026-09-03 10:13:52.164371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '017eead37607'
down_revision: Union[str, Sequence[str], None] = '96f603f00d6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely."""
    # 1. Branch Inventory Table Update
    try:
        with op.batch_alter_table('branch_inventory', schema=None) as batch_op:
            batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f('ix_branch_inventory_product_id'), ['product_id'], unique=False)
    except Exception:
        pass  

    # 2. Order Items Table Update
    try:
        with op.batch_alter_table('order_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f('ix_order_items_product_id'), ['product_id'], unique=False)
    except Exception:
        pass

    # 3. Orders Table - Payment Method
    try:
        with op.batch_alter_table('orders', schema=None) as batch_op:
            batch_op.add_column(sa.Column('payment_method', sa.String(), nullable=True))
    except Exception:
        pass

    # 4. Orders Table - Delivery Address
    try:
        with op.batch_alter_table('orders', schema=None) as batch_op:
            batch_op.add_column(sa.Column('delivery_address', sa.String(), nullable=True))
    except Exception:
        pass

    # 5. Orders Table - Delivery Fee
    try:
        with op.batch_alter_table('orders', schema=None) as batch_op:
            batch_op.add_column(sa.Column('delivery_fee', sa.Float(), nullable=True))
    except Exception:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    pass