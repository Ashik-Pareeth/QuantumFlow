from datetime import datetime
from sqlalchemy.orm import Session
from decimal import Decimal

from db.models import RoundStatus
from domain.pnl import quantize_money
from exceptions.custom_errors import QuantumFlowException
from repositories import (
    candle_repository,
    gamification_repository,
    position_repository,
    user_repository,
    wallet_repository,
)


def create_game_round(
    name: str, start_at: datetime, end_at: datetime, db: Session
) -> dict:
    """Creates a new gamified trading round (Admin function)."""

    if start_at >= end_at:
        raise QuantumFlowException("start_at must be before end_at", status_code=400)

    new_round = gamification_repository.create_round(
        db,
        name=name,
        start_at=start_at,
        end_at=end_at,
        status=RoundStatus.UPCOMING,
    )
    db.commit()

    return {
        "message": f"Round '{name}' created successfully.",
        "round_id": str(new_round.id),
        "status": new_round.status.value,
    }


def get_all_rounds(db: Session) -> list[dict]:
    """Retrieves all historical and active game rounds."""
    rounds = gamification_repository.list_rounds(db)
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
    active_round = gamification_repository.get_active_round(db)
    if not active_round:
        raise QuantumFlowException(
            "No active game round is currently running.", status_code=404
        )

    # 2. Bulk Fetch: Get the absolute latest price for EVERY traded symbol in one query
    active_symbols = position_repository.list_distinct_symbols(db)
    latest_prices = candle_repository.get_latest_prices_by_symbols(db, active_symbols)

    # 3. Calculate Portfolio Value per user in-memory (O(N) complexity)
    wallets = wallet_repository.list_all(db)
    positions = position_repository.list_all(db)

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
                current_price = Decimal(str(latest_prices.get(str(p.symbol), float(str(p.avg_price)))))
                invested_value += Decimal(str(p.qty)) * current_price

        total_value = Decimal(str(wallet.cash_balance)) + invested_value

        # In a real app, we would join the User table to get their display name
        user = user_repository.get_by_id(db, wallet.user_id)
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
        board_entry = gamification_repository.get_leaderboard_entry(
            db, round_id=active_round.id, user_id=data["user_id"]
        )

        if not board_entry:
            gamification_repository.create_leaderboard_entry(
                db,
                round_id=active_round.id,
                user_id=data["user_id"],
                portfolio_value=data["portfolio_value"],
                rank=rank_index,
            )
        else:
            board_entry.portfolio_value = Decimal(str(data["portfolio_value"]))  # type: ignore[assignment]
            board_entry.rank = rank_index  # type: ignore[assignment]

        final_output.append(
            {
                "rank": rank_index,
                "email": data["email"],
                "portfolio_value": str(quantize_money(Decimal(str(data["portfolio_value"])))),
            }
        )

    db.commit()

    return final_output
