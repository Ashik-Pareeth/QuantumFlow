import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from db.database import Base


class RoundStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"


class TradeSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class QuantumFlowEntity(Base):
    """Abstract base class to inherit common UUID and audit tracking fields."""

    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(QuantumFlowEntity):
    __tablename__ = "users"

    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

    # Relationships
    wallet = relationship("Wallet", uselist=False, back_populates="user")
    positions = relationship("Position", back_populates="user")
    trades = relationship("Trade", back_populates="user")
    leaderboard_entries = relationship("Leaderboard", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")


class Wallet(Base):
    __tablename__ = "wallets"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    cash_balance = Column(Numeric(12, 2), default=10000.00, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="wallet")


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

    # Relationships
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

    # Relationships
    user = relationship("User", back_populates="trades")


class GameRound(QuantumFlowEntity):
    __tablename__ = "rounds"

    name = Column(String, nullable=False)
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    status = Column(Enum(RoundStatus), default=RoundStatus.UPCOMING, nullable=False)

    # Relationships
    leaderboard_entries = relationship("Leaderboard", back_populates="round")


class Leaderboard(Base):
    __tablename__ = "leaderboard"

    round_id = Column(
        UUID(as_uuid=True),
        ForeignKey("rounds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    portfolio_value = Column(Numeric(12, 2), nullable=False)
    rank = Column(Integer, nullable=True)
    xp = Column(Integer, default=0, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="leaderboard_entries")
    round = relationship("GameRound", back_populates="leaderboard_entries")


class RefreshToken(QuantumFlowEntity):
    __tablename__ = "refresh_tokens"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")


class Candle(Base):
    """
    Time-Series Hypertable Model.
    Does NOT inherit from QuantumFlowEntity to preserve TimescaleDB partitioning.
    """

    __tablename__ = "candles"

    time = Column(DateTime, primary_key=True, nullable=False, index=True)
    symbol = Column(String, primary_key=True, nullable=False, index=True)
    open = Column(Numeric(10, 4), nullable=False)
    high = Column(Numeric(10, 4), nullable=False)
    low = Column(Numeric(10, 4), nullable=False)
    close = Column(Numeric(10, 4), nullable=False)
    volume = Column(Numeric(14, 2), nullable=False)
