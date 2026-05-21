from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from decimal import Decimal

from db.models import (
    GameRound,
    RoundStatus,
    Leaderboard,
    Wallet,
    Position,
    Candle,
    User,
)
from exceptions.custom_errors import QuantumFlowException


def create_game_round(
    name: str, start_at: datetime, end_at: datetime, db: Session
) -> dict:
    """Creates a new gamified trading round (Admin function)."""

    if start_at >= end_at:
        raise QuantumFlowException("start_at must be before end_at", status_code=400)

    new_round = GameRound(
        name=name, start_at=start_at, end_at=end_at, status=RoundStatus.UPCOMING
    )
    db.add(new_round)
    db.commit()

    return {
        "message": f"Round '{name}' created successfully.",
        "round_id": str(new_round.id),
        "status": new_round.status.value,
    }


def get_all_rounds(db: Session) -> list[dict]:
    """Retrieves all historical and active game rounds."""
    rounds = db.query(GameRound).order_by(desc(GameRound.created_at)).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "status": r.status.value,
            "start_at": r.start_at.isoformat(),
            "end_at": r.end_at.isoformat(),
        }
        for r in rounds
    ]


def calculate_live_leaderboard(db: Session) -> list[dict]:
    """Calculates live PnL for all users and updates the current round standings."""

    # 1. Find the currently active round
    active_round = (
        db.query(GameRound).filter(GameRound.status == RoundStatus.ACTIVE).first()
    )
    if not active_round:
        raise QuantumFlowException(
            "No active game round is currently running.", status_code=404
        )

    # 2. Bulk Fetch: Get the absolute latest price for EVERY traded symbol in one query
    active_symbols = [row[0] for row in db.query(Position.symbol).distinct().all()]
    latest_prices = {}

    if active_symbols:
        candles = (
            db.query(Candle)
            .filter(Candle.symbol.in_(active_symbols))
            .distinct(Candle.symbol)
            .order_by(Candle.symbol, Candle.time.desc())
            .all()
        )
        latest_prices = {c.symbol: c.close for c in candles}

    # 3. Calculate Portfolio Value per user in-memory (O(N) complexity)
    wallets = db.query(Wallet).all()
    positions = db.query(Position).all()

    # Map positions to users for fast lookup
    user_positions = {}
    for p in positions:
        if p.user_id not in user_positions:
            user_positions[p.user_id] = []
        user_positions[p.user_id].append(p)

    rankings = []
    for wallet in wallets:
        invested_value = Decimal("0.00")
        if wallet.user_id in user_positions:
            for p in user_positions[wallet.user_id]:
                current_price = latest_prices.get(p.symbol, p.avg_price)
                invested_value += p.qty * current_price

        total_value = wallet.cash_balance + invested_value

        # In a real app, we would join the User table to get their display name
        user = db.query(User).filter(User.id == wallet.user_id).first()
        email = user.email if user else "Unknown"

        rankings.append(
            {
                "user_id": wallet.user_id,
                "email": email,  # Masking this later in Phase 5
                "portfolio_value": total_value,
            }
        )

    # 4. Sort users by wealth (highest first)
    rankings.sort(key=lambda x: x["portfolio_value"], reverse=True)

    # 5. Upsert rankings into the Leaderboard table
    final_output = []
    for rank_index, data in enumerate(rankings, start=1):
        board_entry = (
            db.query(Leaderboard)
            .filter(
                Leaderboard.round_id == active_round.id,
                Leaderboard.user_id == data["user_id"],
            )
            .first()
        )

        if not board_entry:
            board_entry = Leaderboard(
                round_id=active_round.id,
                user_id=data["user_id"],
                portfolio_value=data["portfolio_value"],
                rank=rank_index,
            )
            db.add(board_entry)
        else:
            board_entry.portfolio_value = data["portfolio_value"]
            board_entry.rank = rank_index

        final_output.append(
            {
                "rank": rank_index,
                "email": data["email"],
                "portfolio_value": str(
                    data["portfolio_value"].quantize(Decimal("0.00"))
                ),
            }
        )

    db.commit()

    return final_output
