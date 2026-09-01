"""add_payment_system_and_tables

Revision ID: 8c66ad25675d
Revises: d03b6580d353
Create Date: 2026-09-01 15:35:22.546630

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c66ad25675d'
down_revision: Union[str, Sequence[str], None] = 'd03b6580d353'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('master_order_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('payment_method', sa.String(), nullable=False),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('transaction_reference', sa.String(), unique=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('payment_date', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['master_order_id'], ['master_order.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'])
    )
    
    op.create_table(
        'merchant_commission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('merchant_id', sa.Integer(), nullable=False),
        sa.Column('gross_amount', sa.Float(), nullable=False),
        sa.Column('commission_rate', sa.Float(), default=0.10),
        sa.Column('commission_amount', sa.Float(), nullable=False),
        sa.Column('merchant_payout', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('payout_date', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']), # Ilisan kon 'order' ang table name sa model
        sa.ForeignKeyConstraint(['merchant_id'], ['users.id'])
    )
    
    op.create_table(
        'bank_transfer_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('bank_name', sa.String(), nullable=False),
        sa.Column('account_name', sa.String(), nullable=False),
        sa.Column('account_number', sa.String(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('reference_number', sa.String(), unique=True),
        sa.Column('status', sa.String(), default='awaiting_payment'),
        sa.Column('payment_deadline', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'])
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('bank_transfer_requests')
    op.drop_table('merchant_commission')
    op.drop_table('payments')