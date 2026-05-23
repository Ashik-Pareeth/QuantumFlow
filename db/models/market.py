from sqlalchemy import Column, DateTime, Numeric, String

from db.models.base import Base


class Candle(Base):
    """
    Time-Series Hypertable Model.
    Does NOT inherit from QuantumFlowEntity to preserve TimescaleDB partitioning.
    """

    __tablename__ = "candles"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol = Column(String, primary_key=True, nullable=False, index=True)
    timeframe = Column(String, primary_key=True, nullable=False)
    open = Column(Numeric(10, 4), nullable=False)
    high = Column(Numeric(10, 4), nullable=False)
    low = Column(Numeric(10, 4), nullable=False)
    close = Column(Numeric(10, 4), nullable=False)
    volume = Column(Numeric(14, 2), nullable=False)
