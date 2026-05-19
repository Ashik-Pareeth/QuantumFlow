from sqlalchemy import Column, String, Float, DateTime, Integer
from db.database import Base


class Candle(Base):
    __tablename__ = "candles"

    time = Column(DateTime(timezone=True), primary_key=True, index=True)
    symbol = Column(String, primary_key=True, index=True)

    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
