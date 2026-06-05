from uuid import UUID

from sqlalchemy.orm import Session

from db.models import Wallet


def get_by_user_id(db: Session, user_id: UUID, *, for_update: bool = False, nowait: bool = False) -> Wallet | None:
    query = db.query(Wallet).filter(Wallet.user_id == user_id)
    if for_update:
        query = query.with_for_update(nowait=nowait)
    return query.first()


def list_all(db: Session) -> list[Wallet]:
    return db.query(Wallet).all()


def create(db: Session, *, user_id: UUID, cash_balance) -> Wallet:
    wallet = Wallet(user_id=user_id, cash_balance=cash_balance)
    db.add(wallet)
    return wallet
