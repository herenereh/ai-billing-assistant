"""Billing use cases on top of the database. Routers stay thin; rules live in billing_calc."""

import math
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schemas
from app.errors import ApiError, not_found
from app.models import Bill, Payment, Subscriber, UsageRecord
from app.services import billing_calc as calc

UNIT_BY_TYPE = {"PHONE": "MIN", "INTERNET": "MB"}
QUANTITY_PER_EVENT = {"PHONE": calc.PHONE_MINUTES_PER_EVENT, "INTERNET": calc.INTERNET_MB_PER_EVENT}


def get_subscriber(db: Session, subscriber_no: str) -> Subscriber:
    sub = db.scalar(select(Subscriber).where(Subscriber.subscriber_no == subscriber_no))
    if sub is None:
        raise not_found("SUBSCRIBER_NOT_FOUND", f"Subscriber {subscriber_no} not found")
    return sub


def _get_bill(db: Session, sub: Subscriber, year: int, month: int, *, for_update: bool = False) -> Bill:
    stmt = select(Bill).where(Bill.subscriber_id == sub.id, Bill.year == year, Bill.month == month)
    if for_update:
        stmt = stmt.with_for_update()  # serialize concurrent payments on Postgres
    bill = db.scalar(stmt)
    if bill is None:
        raise not_found(
            "BILL_NOT_FOUND",
            f"No bill for subscriber {sub.subscriber_no} for {year}-{month:02d}. Calculate the bill first.",
        )
    return bill


def to_summary(sub: Subscriber, bill: Bill) -> schemas.BillSummary:
    return schemas.BillSummary(
        subscriber_no=sub.subscriber_no,
        month=bill.month,
        year=bill.year,
        total=bill.total,
        paid_amount=bill.paid_amount,
        remaining_balance=bill.total - bill.paid_amount,
        status=bill.status,
        due_date=calc.due_date(bill.year, bill.month),
    )


# --- Add Usage --------------------------------------------------------------

def add_usage(db: Session, req: schemas.AddUsageRequest) -> schemas.AddUsageResponse:
    sub = get_subscriber(db, req.subscriber_no)
    usage_type = req.usage_type.value
    quantity = req.count * QUANTITY_PER_EVENT[usage_type]
    db.add(
        UsageRecord(
            subscriber_id=sub.id, year=req.year, month=req.month,
            usage_type=usage_type, events=req.count, quantity=quantity,
        )
    )
    db.commit()
    return schemas.AddUsageResponse(
        subscriber_no=sub.subscriber_no, month=req.month, year=req.year,
        usage_type=req.usage_type, events=req.count, quantity=quantity, unit=UNIT_BY_TYPE[usage_type],
    )


# --- Calculate Bill ---------------------------------------------------------

def _usage_totals(db: Session, sub: Subscriber, year: int, month: int) -> tuple[int, int]:
    rows = db.execute(
        select(UsageRecord.usage_type, func.coalesce(func.sum(UsageRecord.quantity), 0))
        .where(UsageRecord.subscriber_id == sub.id, UsageRecord.year == year, UsageRecord.month == month)
        .group_by(UsageRecord.usage_type)
    ).all()
    totals = {usage_type: int(total) for usage_type, total in rows}
    return totals.get("PHONE", 0), totals.get("INTERNET", 0)


def calculate_bill(db: Session, req: schemas.CalculateBillRequest) -> schemas.CalculateBillResponse:
    """Recompute from recorded usage and upsert. Recalculation keeps any amount already paid."""
    sub = get_subscriber(db, req.subscriber_no)
    minutes, megabytes = _usage_totals(db, sub, req.year, req.month)
    breakdown = calc.calculate_bill(minutes, megabytes)

    bill = db.scalar(
        select(Bill).where(Bill.subscriber_id == sub.id, Bill.year == req.year, Bill.month == req.month)
    )
    if bill is None:
        bill = Bill(subscriber_id=sub.id, year=req.year, month=req.month, paid_amount=Decimal("0.00"))
        db.add(bill)
    bill.phone_minutes = minutes
    bill.internet_mb = megabytes
    bill.phone_charge = breakdown.phone_charge
    bill.internet_charge = breakdown.internet_charge
    bill.total = breakdown.total
    bill.status = calc.bill_status(bill.total, bill.paid_amount)
    db.commit()
    return schemas.CalculateBillResponse(bill=to_summary(sub, bill))


# --- Query Bill / Query Bill Detailed ---------------------------------------

def query_bill(db: Session, subscriber_no: str, year: int, month: int) -> schemas.BillSummary:
    sub = get_subscriber(db, subscriber_no)
    return to_summary(sub, _get_bill(db, sub, year, month))


def query_bill_detailed(
    db: Session, subscriber_no: str, year: int, month: int, page: int, page_size: int
) -> schemas.BillDetailed:
    sub = get_subscriber(db, subscriber_no)
    bill = _get_bill(db, sub, year, month)

    period = (UsageRecord.subscriber_id == sub.id, UsageRecord.year == year, UsageRecord.month == month)
    total_items = db.scalar(select(func.count()).select_from(UsageRecord).where(*period)) or 0
    records = db.scalars(
        select(UsageRecord).where(*period).order_by(UsageRecord.id)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()

    return schemas.BillDetailed(
        **to_summary(sub, bill).model_dump(),
        usage=schemas.UsageTotals(
            phone_minutes=bill.phone_minutes,
            internet_mb=bill.internet_mb,
            internet_gb=bill.internet_mb / calc.MB_PER_GB,
        ),
        charges=schemas.ChargeBreakdown(
            phone_charge=bill.phone_charge, internet_charge=bill.internet_charge, total=bill.total
        ),
        usage_records=schemas.Page[schemas.UsageRecordOut](
            items=[
                schemas.UsageRecordOut(
                    id=r.id, usage_type=schemas.UsageType(r.usage_type), events=r.events, quantity=r.quantity,
                    unit=UNIT_BY_TYPE[r.usage_type], recorded_at=r.created_at.isoformat(),
                )
                for r in records
            ],
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=math.ceil(total_items / page_size) if total_items else 0,
        ),
    )


# --- Pay Bill ---------------------------------------------------------------

def pay_bill(db: Session, subscriber_no: str, req: schemas.PayBillRequest) -> schemas.PayBillResponse:
    if db.scalar(select(Payment.id).where(Payment.transaction_id == req.transaction_id)) is not None:
        raise ApiError(409, "DUPLICATE_TRANSACTION", f"Transaction {req.transaction_id} was already processed")

    sub = get_subscriber(db, subscriber_no)
    bill = _get_bill(db, sub, req.year, req.month, for_update=True)
    try:
        calc.validate_payment(req.amount, bill.total, bill.paid_amount)
    except ValueError as exc:
        raise ApiError(400, "INVALID_PAYMENT", str(exc))

    bill.paid_amount = bill.paid_amount + req.amount
    bill.status = calc.bill_status(bill.total, bill.paid_amount)
    db.add(Payment(bill_id=bill.id, transaction_id=req.transaction_id, amount=req.amount, status="SUCCESS"))
    try:
        db.commit()
    except IntegrityError:  # lost a race on the unique transaction_id
        db.rollback()
        raise ApiError(409, "DUPLICATE_TRANSACTION", f"Transaction {req.transaction_id} was already processed")

    return schemas.PayBillResponse(
        transaction_id=req.transaction_id,
        amount=req.amount,
        paid_amount=bill.paid_amount,
        remaining_balance=bill.total - bill.paid_amount,
        bill_status=bill.status,
    )
