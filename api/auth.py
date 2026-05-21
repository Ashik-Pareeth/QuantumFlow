from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from db.database import get_db
from api.schemas import UserRegisterRequest
from services.auth_service import register_new_user

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user and seeds their gamified wallet."""
    return register_new_user(
        username=request.username, email=request.email, password=request.password, db=db
    )
