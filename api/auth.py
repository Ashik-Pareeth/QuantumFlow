from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from db.database import get_db
from api.schemas import UserRegisterRequest
from services.auth_service import register_new_user, authenticate_user
from core.security import create_access_token

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user and seeds their gamified wallet."""
    return register_new_user(
        username=request.username, email=request.email, password=request.password, db=db
    )


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Authenticates a user via email OR username and returns a JWT access token."""

    # form_data.username contains whatever the user typed into the login box
    user = authenticate_user(
        login_identifier=form_data.username, password=form_data.password, db=db
    )

    # Generate the JWT token containing the user's UUID
    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "username": user.username, "email": user.email},
    }
