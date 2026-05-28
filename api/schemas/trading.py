from decimal import Decimal
from uuid import UUID
from pandas_ta.core import Optional
from pydantic import BaseModel, Field, model_validator

from db.models import TradeSide


class TradeRequest(BaseModel):
    symbol: str

    # 2. Apply the Enum to the side field
    side: TradeSide

    qty: Optional[Decimal] = Field(
        default=None, gt=0, description="Number of shares to trade"
    )
    notional_value: Optional[Decimal] = Field(
        default=None, gt=0, description="Amount in USD to spend/receive"
    )
    force_execution: bool = False
    idempotency_key: Optional[str] = Field(
        default=None, description="Unique UUID to prevent double-charging"
    )

    @model_validator(mode="after")
    def check_exclusive_fields(self):
        has_qty = self.qty is not None
        has_notional = self.notional_value is not None

        if not (has_qty ^ has_notional):  # XOR operator
            raise ValueError(
                "You must specify EXACTLY ONE of 'qty' (shares) "
                "or 'notional_value' (dollars)."
            )

        return self


class SellTradeRequest(TradeRequest):
    user_id: UUID


class LegacyTradeRequest(TradeRequest):
    user_id: UUID
    side: TradeSide
