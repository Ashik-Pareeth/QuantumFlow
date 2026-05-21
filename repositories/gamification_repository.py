from sqlalchemy import desc
from sqlalchemy.orm import Session

from db.models import GameRound, Leaderboard, RoundStatus


def create_round(db: Session, *, name: str, start_at, end_at, status: RoundStatus) -> GameRound:
    round_ = GameRound(name=name, start_at=start_at, end_at=end_at, status=status)
    db.add(round_)
    return round_


def list_rounds(db: Session) -> list[GameRound]:
    return db.query(GameRound).order_by(desc(GameRound.created_at)).all()


def get_active_round(db: Session) -> GameRound | None:
    return db.query(GameRound).filter(GameRound.status == RoundStatus.ACTIVE).first()


def get_leaderboard_entry(db: Session, *, round_id, user_id) -> Leaderboard | None:
    return (
        db.query(Leaderboard)
        .filter(Leaderboard.round_id == round_id, Leaderboard.user_id == user_id)
        .first()
    )


def create_leaderboard_entry(db: Session, *, round_id, user_id, portfolio_value, rank: int) -> Leaderboard:
    entry = Leaderboard(
        round_id=round_id,
        user_id=user_id,
        portfolio_value=portfolio_value,
        rank=rank,
    )
    db.add(entry)
    return entry
