from pydantic import BaseModel, Field
from uuid import UUID
from decimal import Decimal
from datetime import datetime


class TradeRequest(BaseModel):
    user_id: UUID  # Temporary for Phase 4 (Replaced by JWT later)
    symbol: str
    qty: Decimal = Field(..., gt=0, description="Quantity must be greater than zero")
    force_execution: bool = Field(default=False, description="Bypass Risk Gate")


class GameRoundCreate(BaseModel):
    name: str = Field(
        ..., description="Name of the trading round, e.g., 'Alpha Sprint'"
    )
    start_at: datetime
    end_at: datetime
