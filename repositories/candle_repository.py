from sqlalchemy.orm import Session

from db.models import Candle


def get_latest_for_symbol(db: Session, symbol: str) -> Candle | None:
    return (
        db.query(Candle)
        .filter(Candle.symbol == symbol)
        .order_by(Candle.time.desc())
        .first()
    )


def get_recent_for_symbol(db: Session, symbol: str, limit: int) -> list[Candle]:
    return (
        db.query(Candle)
        .filter(Candle.symbol == symbol.upper())
        .order_by(Candle.time.desc())
        .limit(limit)
        .all()
    )


def get_chronological_for_symbol(db: Session, symbol: str, limit: int) -> list[Candle]:
    return (
        db.query(Candle)
        .filter(Candle.symbol == symbol.upper())
        .order_by(Candle.time.asc())
        .limit(limit)
        .all()
    )


def get_latest_prices_by_symbols(db: Session, symbols: list[str]) -> dict[str, object]:
    if not symbols:
        return {}

    candles = (
        db.query(Candle)
        .filter(Candle.symbol.in_(symbols))
        .distinct(Candle.symbol)
        .order_by(Candle.symbol, Candle.time.desc())
        .all()
    )
    return {c.symbol: c.close for c in candles}


def replace_for_symbol(db: Session, symbol: str, candles: list[Candle]) -> None:
    db.query(Candle).filter(Candle.symbol == symbol.upper()).delete()
    db.add_all(candles)
