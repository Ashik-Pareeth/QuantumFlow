from sqlalchemy import or_
from sqlalchemy.orm import Session

from db.models import User


def get_by_id(db: Session, user_id) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_by_email_or_username(db: Session, identifier: str) -> User | None:
    return (
        db.query(User)
        .filter(or_(User.email == identifier, User.username == identifier))
        .first()
    )


def get_by_email_or_username_pair(
    db: Session, *, email: str, username: str
) -> User | None:
    return (
        db.query(User)
        .filter(or_(User.email == email, User.username == username))
        .first()
    )


def create(db: Session, *, username: str, email: str, password_hash: str) -> User:
    user = User(username=username, email=email, password=password_hash)
    db.add(user)
    return user
