from datetime import datetime, timedelta, timezone
from typing import Annotated
from pydantic import AfterValidator
import nh3

from jose import jwt

from core.config import settings

SECRET_KEY = settings.secret_key.get_secret_value()
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


def create_access_token(data: dict) -> str:
    """Generates a secure JWT token for an authenticated user."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def strip_xss(value: str) -> str:
    """
    Strips all HTML tags and executable JavaScript from a string.
    """
    if not isinstance(value, str):
        return value

    # nh3.clean completely removes malicious tags like <script> or <iframe>
    # while safely keeping standard text intact.
    return nh3.clean(value)


# Define a custom Pydantic type
SafeString = Annotated[str, AfterValidator(strip_xss)]
