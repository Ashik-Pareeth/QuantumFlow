from uuid import UUID

from sqlalchemy.orm import Session

from db.models import Position


def get_by_user_and_symbol(
    db: Session,
    user_id: UUID,
    symbol: str,
    *,
    for_update: bool = False,
) -> Position | None:
    query = db.query(Position).filter(
        Position.user_id == user_id,
        Position.symbol == symbol,
    )
    if for_update:
        query = query.with_for_update()
    return query.first()


def list_for_user(db: Session, user_id: UUID) -> list[Position]:
    return db.query(Position).filter(Position.user_id == user_id).all()


def list_all(db: Session) -> list[Position]:
    return db.query(Position).all()


def list_distinct_symbols(db: Session) -> list[str]:
    return [row[0] for row in db.query(Position.symbol).distinct().all()]


def create(db: Session, *, user_id: UUID, symbol: str, qty, avg_price) -> Position:
    position = Position(user_id=user_id, symbol=symbol, qty=qty, avg_price=avg_price)
    db.add(position)
    return position


def delete(db: Session, position: Position) -> None:
    db.delete(position)
