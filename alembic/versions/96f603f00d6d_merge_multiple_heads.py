"""Merge multiple heads

Revision ID: 96f603f00d6d
Revises: 8c66ad25675d, eca97cb83736
Create Date: 2026-09-01 15:47:21.417027

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96f603f00d6d'
down_revision: Union[str, Sequence[str], None] = ('8c66ad25675d', 'eca97cb83736')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
