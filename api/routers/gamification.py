from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.schemas.gamification import GameRoundCreate
from db.database import get_db
from services.gamification_service import (
    calculate_live_leaderboard,
    create_game_round,
    get_all_rounds,
)

router = APIRouter()


@router.post("/rounds", status_code=status.HTTP_201_CREATED)
def start_new_round(request: GameRoundCreate, db: Session = Depends(get_db)):
    """Admin: Creates a new trading round."""
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
    return calculate_live_leaderboard(db=db)
