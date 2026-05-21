from pydantic import BaseModel, Field, EmailStr
from decimal import Decimal
from datetime import datetime


class TradeRequest(BaseModel):
    symbol: str
    qty: Decimal = Field(..., gt=0, description="Quantity must be greater than zero")
    force_execution: bool = Field(default=False)


class GameRoundCreate(BaseModel):
    name: str = Field(
        ..., description="Name of the trading round, e.g., 'Alpha Sprint'"
    )
    start_at: datetime
    end_at: datetime


class UserRegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=20,
        description="Public display name for the leaderboard",
    )
    email: EmailStr
    password: str = Field(
        ..., min_length=8, description="Password must be at least 8 characters"
    )
