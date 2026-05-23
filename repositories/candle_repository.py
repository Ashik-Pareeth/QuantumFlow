from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from db.models.market import Candle


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
    """Get the most recent close price for each symbol."""

    if not symbols:
        return {}

    # 1. Find the exact latest timestamp for each symbol
    subquery = (
        db.query(Candle.symbol, func.max(Candle.time).label("max_time"))
        .filter(Candle.symbol.in_(symbols))
        .group_by(Candle.symbol)
        .subquery()
    )

    # 2. Join back to the Candle table to get the close price at that exact time
    latest_candles = (
        db.query(Candle)
        .join(
            subquery,
            (Candle.symbol == subquery.c.symbol) & (Candle.time == subquery.c.max_time),
        )
        .all()
    )

    return {c.symbol: float(c.close) for c in latest_candles}


def upsert_candles(db: Session, records: list[dict]):
    """
    Performs a PostgreSQL UPSERT. Inserts new candles safely.
    If a candle with the exact same time, symbol, and timeframe already exists,
    it completely ignores it to prevent IntegrityErrors.
    """
    if not records:
        return

    # Create the PostgreSQL-specific Insert statement
    stmt = insert(Candle).values(records)

    # THE UPSERT: Block duplicates at the database level
    stmt = stmt.on_conflict_do_nothing(index_elements=["time", "symbol", "timeframe"])

    db.execute(stmt)
    db.commit()
