from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from db.database import get_db
from api.schemas import GameRoundCreate
from services.gamification_service import (
    create_game_round,
    get_all_rounds,
    calculate_live_leaderboard,
)

router = APIRouter()


@router.post("/rounds", status_code=status.HTTP_201_CREATED)
def start_new_round(request: GameRoundCreate, db: Session = Depends(get_db)):
    """Admin: Creates a new trading round."""
    # TODO: In Phase 5, protect this route with a require_role('admin') dependency
    return create_game_round(
        name=request.name, start_at=request.start_at, end_at=request.end_at, db=db
    )


@router.get("/rounds")
def list_rounds(db: Session = Depends(get_db)):
    """Public: Lists all game rounds."""
    return get_all_rounds(db=db)


@router.get("/leaderboard/live")
def get_live_leaderboard(db: Session = Depends(get_db)):
    """Public: Calculates and retrieves the live leaderboard for the active round."""
    # NOTE: In production, this route would just read from Redis, and the calculation
    # would be handled by an async background worker.
    # For Phase 4, we calculate on-demand.
    return calculate_live_leaderboard(db=db)
