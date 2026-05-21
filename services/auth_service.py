from sqlalchemy.orm import Session
from passlib.context import CryptContext
from sqlalchemy import or_

from db.models import User, Wallet
from exceptions.custom_errors import QuantumFlowException, InvalidCredentialsError

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

    # 1. Check if user already exists

    existing_user = (
        db.query(User)
        .filter(or_(User.email == email, User.username == username))
        .first()
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
        # 2. Create the User with a securely hashed password
        hashed_password = get_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        db.add(new_user)

        # db.flush() pushes the insert to Postgres without fully committing it.
        # This allows Postgres to generate the UUID, which we need for the Wallet.
        db.flush()

        # 3. Auto-Create the Gamified Wallet
        new_wallet = Wallet(user_id=new_user.id, cash_balance=10000.00)
        db.add(new_wallet)

        # 4. Commit the entire transaction atomically
        db.commit()

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
        }

    except Exception as e:
        db.rollback()
        raise e


def authenticate_user(login_identifier: str, password: str, db: Session):
    """Validates user credentials against the database."""
    user = (
        db.query(User)
        .filter(or_(User.email == login_identifier, User.username == login_identifier))
        .first()
    )

    if not user:
        raise InvalidCredentialsError()

    if not verify_password(password, user.password):
        raise InvalidCredentialsError()

    return user
