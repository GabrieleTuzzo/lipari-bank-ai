import sqlite3
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models import Account, Beneficiary, Card, Customer, Mandate
from src.db.session import Base


def test_mandate_preserves_beneficiary_and_card_plafond() -> None:
    customer_id = uuid4().hex[:16]
    account_id = f"IT{uuid4().hex}"
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection: sqlite3.Connection, _record: object) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    beneficiary = Beneficiary(
        customer_id=customer_id,
        full_name="Beneficiario di prova",
        iban=f"IT{uuid4().hex}",
    )
    try:
        with Session(engine) as session:
            session.add(Customer(id=customer_id, full_name="Cliente di prova", operator="test"))
            session.flush()
            session.add(
                Account(
                    id=account_id,
                    customer_id=customer_id,
                    label="principale",
                    balance=Decimal("100.00"),
                )
            )
            session.add(beneficiary)
            session.flush()
            card = Card(account_id=account_id, plafond=Decimal("1250.00"))
            mandate = Mandate(
                account_id=account_id,
                beneficiary_id=beneficiary.id,
                reference=f"MANDATE-{uuid4().hex}",
            )
            session.add_all([card, mandate])
            session.flush()
            assert session.scalar(select(Card.plafond).where(Card.id == card.id)) == Decimal(
                "1250.00"
            )
            session.commit()

            with pytest.raises(IntegrityError):
                with session.begin():
                    session.delete(beneficiary)
    finally:
        engine.dispose()
