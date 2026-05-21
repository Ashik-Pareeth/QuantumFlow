from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from db.models import TradeSide


class TradeRequest(BaseModel):
    symbol: str
    qty: Decimal = Field(..., gt=0, description="Quantity must be greater than zero")
    force_execution: bool = Field(default=False)


class SellTradeRequest(TradeRequest):
    user_id: UUID


class LegacyTradeRequest(TradeRequest):
    user_id: UUID
    side: TradeSide
