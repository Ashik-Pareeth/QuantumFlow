from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from db.models import Trade, TradeSide


def create(
    db: Session,
    *,
    user_id: UUID,
    symbol: str,
    side: TradeSide,
    qty,
    price,
    pnl,
) -> Trade:
    trade = Trade(
        user_id=user_id,
        symbol=symbol,
        side=side,
        qty=qty,
        price=price,
        pnl=pnl,
    )
    db.add(trade)
    return trade


def list_for_user(db: Session, user_id: UUID, limit: int) -> list[Trade]:
    return (
        db.query(Trade)
        .filter(Trade.user_id == user_id)
        .order_by(desc(Trade.created_at))
        .limit(limit)
        .all()
    )
