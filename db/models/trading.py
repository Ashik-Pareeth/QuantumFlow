import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.models.base import Base, QuantumFlowEntity


class TradeSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class Position(Base):
    __tablename__ = "positions"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    symbol = Column(String, primary_key=True, index=True)
    qty = Column(Numeric(12, 4), default=0, nullable=False)
    avg_price = Column(Numeric(10, 4), default=0.0000, nullable=False)
    opened_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = relationship("User", back_populates="positions")


class Trade(QuantumFlowEntity):
    __tablename__ = "trades"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    symbol = Column(String, index=True, nullable=False)
    side = Column(Enum(TradeSide), nullable=False)
    qty = Column(Numeric(12, 4), nullable=False)
    price = Column(Numeric(10, 4), nullable=False)
    pnl = Column(Numeric(12, 2), default=0.00, nullable=False)

    user = relationship("User", back_populates="trades")
