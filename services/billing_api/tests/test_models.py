"""Schema-level tests: constraints that protect billing data, run on in-memory SQLite."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Bill, Payment, Subscriber, UsageRecord


@pytest.fixture
def session():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _subscriber(s, no="5551001", role="SUBSCRIBER"):
    sub = Subscriber(subscriber_no=no, full_name="Test User", password_hash="x", role=role)
    s.add(sub)
    s.flush()
    return sub


def _bill(s, sub, year=2026, month=10):
    bill = Bill(
        subscriber_id=sub.id, year=year, month=month, phone_minutes=1350, internet_mb=35000,
        phone_charge=Decimal("10"), internet_charge=Decimal("70"), total=Decimal("80"),
        paid_amount=Decimal("0"), status="UNPAID",
    )
    s.add(bill)
    s.flush()
    return bill


def test_full_graph_persists(session):
    sub = _subscriber(session)
    session.add(UsageRecord(subscriber_id=sub.id, year=2026, month=10, usage_type="PHONE", events=1, quantity=10))
    bill = _bill(session, sub)
    session.add(Payment(bill_id=bill.id, transaction_id="tx-1", amount=Decimal("30")))
    session.commit()
    assert session.get(Bill, bill.id).payments[0].amount == Decimal("30")
    assert len(session.get(Subscriber, sub.id).usage_records) == 1


def test_duplicate_subscriber_no_rejected(session):
    _subscriber(session, "5551001")
    with pytest.raises(IntegrityError):
        _subscriber(session, "5551001")


def test_one_bill_per_subscriber_period(session):
    sub = _subscriber(session)
    _bill(session, sub)
    with pytest.raises(IntegrityError):
        _bill(session, sub)


def test_duplicate_transaction_id_rejected(session):
    bill = _bill(session, _subscriber(session))
    session.add(Payment(bill_id=bill.id, transaction_id="tx-dup", amount=Decimal("10")))
    session.flush()
    session.add(Payment(bill_id=bill.id, transaction_id="tx-dup", amount=Decimal("10")))
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"usage_type": "SMS", "month": 10, "events": 1, "quantity": 1},
        {"usage_type": "PHONE", "month": 13, "events": 1, "quantity": 10},
        {"usage_type": "PHONE", "month": 10, "events": 0, "quantity": 0},
    ],
)
def test_invalid_usage_rejected(session, kwargs):
    sub = _subscriber(session)
    session.add(UsageRecord(subscriber_id=sub.id, year=2026, **kwargs))
    with pytest.raises(IntegrityError):
        session.flush()


def test_usage_for_unknown_subscriber_rejected(session):
    session.add(UsageRecord(subscriber_id=999, year=2026, month=10, usage_type="PHONE", events=1, quantity=10))
    with pytest.raises(IntegrityError):
        session.flush()
