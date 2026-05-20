from pydantic import BaseModel, Field
from uuid import UUID
from decimal import Decimal
from db.models import TradeSide


class TradeRequest(BaseModel):
    user_id: UUID
    symbol: str
    side: TradeSide  # Accepts "buy" or "sell"
    qty: Decimal = Field(..., gt=0, description="Quantity must be greater than zero")
    force_execution: bool = Field(default=False)
