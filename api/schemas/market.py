from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CandleResponse(BaseModel):
    time: datetime
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
