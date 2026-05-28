from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from api.schemas.user import UserRegisterRequest, UserRegisterResponse
from core.rate_limiter import limiter
from db.database import get_db
from services.auth_service import authenticate_user, register_new_user

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """Registers a new user and seeds their gamified wallet."""
    return register_new_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        db=db,
    )


@router.post(
    "/login", response_model=UserRegisterResponse, status_code=status.HTTP_200_OK
)
@limiter.limit("10/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticates a user via email OR username and returns a JWT access token."""
    user = authenticate_user(
        email_or_username=form_data.username, password=form_data.password, db=db
    )
    return user
