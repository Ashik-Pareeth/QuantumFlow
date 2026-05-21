from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from db.database import get_db
from db.models.user import User
from core.security import SECRET_KEY, ALGORITHM
from exceptions.custom_errors import AuthenticationFailedError

# This tells FastAPI where the frontend should go to get a token.
# It automatically wires up the Swagger UI "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Intercepts requests, validates the JWT, and returns the User object."""

    try:
        # 1. Decode the token using our secret key
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 2. Extract the user_id (which we stored in the "sub" claim)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise AuthenticationFailedError(detail="Token payload invalid.")

    except JWTError:
        raise AuthenticationFailedError(detail="Could not validate credentials.")

    # 3. Fetch the actual user from the database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AuthenticationFailedError(detail="User no longer exists.")

    return user
