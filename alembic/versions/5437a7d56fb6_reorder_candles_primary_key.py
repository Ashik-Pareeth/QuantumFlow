"""reorder candles primary key

Revision ID: 5437a7d56fb6
Revises: baedc8eba33e
Create Date: 2026-05-24 20:17:05.020339

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5437a7d56fb6"
down_revision: Union[str, Sequence[str], None] = "baedc8eba33e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the existing primary key constraint
    op.drop_constraint("candles_pkey", "candles", type_="primary")

    # 2. Recreate it with the mathematically optimized order!
    op.create_primary_key("candles_pkey", "candles", ["symbol", "timeframe", "time"])


def downgrade() -> None:
    # Revert back to the unoptimized order if we rollback
    op.drop_constraint("candles_pkey", "candles", type_="primary")
    op.create_primary_key("candles_pkey", "candles", ["time", "symbol", "timeframe"])
