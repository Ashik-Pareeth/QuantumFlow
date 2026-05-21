from datetime import datetime

from pydantic import BaseModel, Field


class GameRoundCreate(BaseModel):
    name: str = Field(
        ..., description="Name of the trading round, e.g., 'Alpha Sprint'"
    )
    start_at: datetime
    end_at: datetime
