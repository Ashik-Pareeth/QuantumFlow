import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.models.base import Base, QuantumFlowEntity


class RoundStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"


class GameRound(QuantumFlowEntity):
    __tablename__ = "rounds"

    name = Column(String, nullable=False)
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    status = Column(Enum(RoundStatus), default=RoundStatus.UPCOMING, nullable=False)

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
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="leaderboard_entries")
    round = relationship("GameRound", back_populates="leaderboard_entries")
