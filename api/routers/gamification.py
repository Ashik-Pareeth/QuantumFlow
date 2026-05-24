from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from api.schemas.gamification import GameRoundCreate
from core.rate_limiter import limiter
from db.database import get_db
from services.gamification_service import (
    calculate_live_leaderboard,
    create_game_round,
    get_all_rounds,
)

router = APIRouter()


@router.post("/rounds", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def start_new_round(
    request: Request,
    payload: GameRoundCreate,
    db: Session = Depends(get_db),
):
    """Admin: Creates a new trading round."""
    return create_game_round(
        name=payload.name,
        start_at=payload.start_at,
        end_at=payload.end_at,
        db=db,
    )


@router.get("/rounds")
@limiter.limit("60/minute")
def list_rounds(request: Request, db: Session = Depends(get_db)):
    """Public: Lists all game rounds."""
    return get_all_rounds(db=db)


@router.get("/leaderboard/live")
@limiter.limit("60/minute")
def get_live_leaderboard(request: Request, db: Session = Depends(get_db)):
    """Public: Calculates and retrieves the live leaderboard for the active round."""
    return calculate_live_leaderboard(db=db)
