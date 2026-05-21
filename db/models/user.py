from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.models.base import Base, QuantumFlowEntity


class User(QuantumFlowEntity):
    __tablename__ = "users"

    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

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

    user = relationship("User", back_populates="wallet")


class RefreshToken(QuantumFlowEntity):
    __tablename__ = "refresh_tokens"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")
