"""Load demo data (fictitious, test-only credentials). Safe to run more than once.

    uv run python -m app.seed

Scenario data:
- 5551001: Sep 2026 = $50 (paid in full); Oct 2026 = 1,350 min + 35 GB = $80 (unpaid)
  → "Why is my October bill higher?" and "Pay my bill".
- 5551002: Oct 2026 = 2,200 min + 21 GB = $20 + $60 = $80, partially paid $30.
- ADMIN001: administrator for Add Usage / Calculate Bill.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.auth import ROLE_ADMIN, ROLE_SUBSCRIBER, hash_password
from app.db import SessionLocal
from app.models import Subscriber, UsageRecord
from app.services import bill_service

# Test-only credentials for local/demo use. Documented in the README.
USERS = [
    ("ADMIN001", "Billing Admin", "Admin#2026", ROLE_ADMIN),
    ("5551001", "Ayse Demo", "Demo#1001", ROLE_SUBSCRIBER),
    ("5551002", "Mert Demo", "Demo#1002", ROLE_SUBSCRIBER),
]

# (subscriber_no, year, month, phone_minutes_chunks, internet_mb_chunks)
USAGE = [
    ("5551001", 2026, 9, [200, 300, 300], [6_000, 6_000, 6_000]),             # 800 min, 18 GB → $50
    ("5551001", 2026, 10, [150] * 9, [5_000] * 7),                            # 1,350 min, 35 GB → $80
    ("5551002", 2026, 10, [400, 600, 600, 600], [7_000, 7_000, 7_000]),       # 2,200 min, 21 GB → $80
]

# (subscriber_no, year, month, amount, transaction_id)
PAYMENTS = [
    ("5551001", 2026, 9, Decimal("50.00"), "seed-5551001-202609-full"),
    ("5551002", 2026, 10, Decimal("30.00"), "seed-5551002-202610-part"),
]


def seed(db: Session) -> None:
    existing = set(db.scalars(select(Subscriber.subscriber_no)))
    if "5551001" in existing:
        print("Seed data already present; nothing to do.")
        return

    for no, name, password, role in USERS:
        if no not in existing:
            db.add(Subscriber(subscriber_no=no, full_name=name, password_hash=hash_password(password), role=role))
    db.flush()

    subscribers = {s.subscriber_no: s for s in db.scalars(select(Subscriber))}
    for no, year, month, minute_chunks, mb_chunks in USAGE:
        sub_id = subscribers[no].id
        for minutes in minute_chunks:
            db.add(UsageRecord(subscriber_id=sub_id, year=year, month=month, usage_type="PHONE",
                               events=minutes // 10, quantity=minutes))
        for mb in mb_chunks:
            db.add(UsageRecord(subscriber_id=sub_id, year=year, month=month, usage_type="INTERNET",
                               events=mb, quantity=mb))
    db.commit()

    for no, year, month, *_ in USAGE:
        bill = bill_service.calculate_bill(db, schemas.CalculateBillRequest(subscriber_no=no, month=month, year=year))
        print(f"{no} {year}-{month:02d}: total ${bill.bill.total}")

    for no, year, month, amount, tx in PAYMENTS:
        bill_service.pay_bill(db, no, schemas.PayBillRequest(month=month, year=year, amount=amount, transaction_id=tx))
    print("Seed complete.")


if __name__ == "__main__":
    with SessionLocal() as session:
        seed(session)
