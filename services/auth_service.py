from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt

from core.security import ALGORITHM, SECRET_KEY, create_access_token
from exceptions.custom_errors import QuantumFlowException, InvalidCredentialsError
from exceptions.custom_errors import AuthenticationFailedError
from repositories import user_repository, wallet_repository

# Configure bcrypt as the hashing algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hashes a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against the hashed version."""
    return pwd_context.verify(plain_password, hashed_password)


def register_new_user(username: str, email: str, password: str, db: Session) -> dict:
    """Registers a user, hashes their password, and seeds their initial wallet."""

    existing_user = user_repository.get_by_email_or_username_pair(
        db, email=email, username=username
    )

    if existing_user:
        if existing_user.email == email:
            raise QuantumFlowException(
                message="Email is already registered.", status_code=409
            )
        if existing_user.username == username:
            raise QuantumFlowException(
                message="Username is already taken.", status_code=409
            )

    try:
        hashed_password = get_password_hash(password)
        new_user = user_repository.create(
            db, username=username, email=email, password_hash=hashed_password
        )

        db.flush()

        wallet_repository.create(db, user_id=new_user.id, cash_balance=10000.00)

        db.commit()

        access_token = create_access_token(data={"sub": str(new_user.id)})

        return {
            "message": "User registered successfully.",
            "paper_trading": {
                "starting_capital": 10000,
                "currency": "USD",
                "status": "credited",
            },
            "user": {
                "id": str(new_user.id),
                "username": new_user.username,
                "email": new_user.email,
            },
            "access_token": access_token,
            "token_type": "bearer",
        }

    except Exception as e:
        db.rollback()
        raise e


def authenticate_user(login_identifier: str, password: str, db: Session):
    """Validates user credentials against the database."""
    user = user_repository.get_by_email_or_username(db, login_identifier)

    if not user:
        raise InvalidCredentialsError()

    if not verify_password(password, user.password):
        raise InvalidCredentialsError()

    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
        },
    }


def get_user_from_access_token(token: str, db: Session):
    """Validates an access token and returns the authenticated user."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise AuthenticationFailedError(detail="Token payload invalid.")

    except JWTError:
        raise AuthenticationFailedError(detail="Could not validate credentials.")

    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise AuthenticationFailedError(detail="User no longer exists.")

    return user
