from pydantic import BaseModel, Field
from uuid import UUID
from decimal import Decimal


class BuyTradeRequest(BaseModel):
    user_id: UUID  # Temporary for Phase 4
    symbol: str
    qty: Decimal = Field(..., gt=0, description="Quantity must be greater than zero")
    force_execution: bool = Field(
        default=False, description="Set to true to bypass HMM Risk Gate warnings"
    )
