from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from db.database import get_db
from db.models.user import User
from services.auth_service import get_user_from_access_token

# This tells FastAPI where the frontend should go to get a token.
# It automatically wires up the Swagger UI "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Intercepts requests, validates the JWT, and returns the User object."""
    return get_user_from_access_token(token=token, db=db)
