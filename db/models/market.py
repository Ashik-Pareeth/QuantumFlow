from sqlalchemy import Column, DateTime, Numeric, PrimaryKeyConstraint, String

from db.models.base import Base


class Candle(Base):
    """
    Time-Series Hypertable Model.
    Does NOT inherit from QuantumFlowEntity to preserve TimescaleDB partitioning.
    """

    __tablename__ = "candles"

    time = Column(DateTime(timezone=True), nullable=False)
    symbol = Column(String, nullable=False, index=True)
    timeframe = Column(String, nullable=False)

    open = Column(Numeric(10, 4), nullable=False)
    high = Column(Numeric(10, 4), nullable=False)
    low = Column(Numeric(10, 4), nullable=False)
    close = Column(Numeric(10, 4), nullable=False)
    volume = Column(Numeric(14, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("symbol", "timeframe", "time", name="candles_pkey"),
    )
