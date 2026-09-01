"""Add payment system and inventory tracking

Revision ID: eca97cb83736
Revises: 8c0d8905d545
Create Date: 2026-09-01 15:43:18.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'eca97cb83736'
down_revision = '8c0d8905d545'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('master_order_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('payment_method', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('transaction_reference', sa.String(), unique=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('payment_date', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['master_order_id'], ['master_order.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'])
    )
    
    op.create_table(
        'merchant_commission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('merchant_id', sa.Integer(), nullable=False),
        sa.Column('gross_amount', sa.Float(), nullable=False),
        sa.Column('commission_rate', sa.Float(), server_default=sa.text('0.10'), nullable=False),
        sa.Column('commission_amount', sa.Float(), nullable=False),
        sa.Column('merchant_payout', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('payout_date', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['order_id'], ['order.id']),
        sa.ForeignKeyConstraint(['merchant_id'], ['user.id'])
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
        sa.Column('status', sa.String(), server_default=sa.text("'awaiting_payment'"), nullable=False),
        sa.Column('payment_deadline', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['order_id'], ['order.id'])
    )


def downgrade():
    op.drop_table('bank_transfer_requests')
    op.drop_table('merchant_commission')
    op.drop_table('payments')