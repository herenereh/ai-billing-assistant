"""ER model: subscriber 1─* usage_record, subscriber 1─* bill, bill 1─* payment."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

Money = Numeric(10, 2)


class Subscriber(Base):
    __tablename__ = "subscriber"
    __table_args__ = (CheckConstraint("role IN ('SUBSCRIBER', 'ADMIN')", name="ck_subscriber_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber_no: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="SUBSCRIBER")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usage_records: Mapped[list["UsageRecord"]] = relationship(back_populates="subscriber")
    bills: Mapped[list["Bill"]] = relationship(back_populates="subscriber")


class UsageRecord(Base):
    """One row per Add Usage call. quantity = events × fixed unit (10 min or 1 MB)."""

    __tablename__ = "usage_record"
    __table_args__ = (
        CheckConstraint("usage_type IN ('PHONE', 'INTERNET')", name="ck_usage_type"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_usage_month"),
        CheckConstraint("events > 0 AND quantity > 0", name="ck_usage_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscriber.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    usage_type: Mapped[str] = mapped_column(String(10))
    events: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)  # minutes for PHONE, MB for INTERNET
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subscriber: Mapped[Subscriber] = relationship(back_populates="usage_records")


class Bill(Base):
    __tablename__ = "bill"
    __table_args__ = (
        UniqueConstraint("subscriber_id", "year", "month", name="uq_bill_period"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_bill_month"),
        CheckConstraint("status IN ('UNPAID', 'PARTIAL', 'PAID')", name="ck_bill_status"),
        CheckConstraint("paid_amount >= 0", name="ck_bill_paid_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscriber.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    phone_minutes: Mapped[int] = mapped_column(Integer)
    internet_mb: Mapped[int] = mapped_column(Integer)
    phone_charge: Mapped[Decimal] = mapped_column(Money)
    internet_charge: Mapped[Decimal] = mapped_column(Money)
    total: Mapped[Decimal] = mapped_column(Money)
    paid_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(10), default="UNPAID")
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    subscriber: Mapped[Subscriber] = relationship(back_populates="bills")
    payments: Mapped[list["Payment"]] = relationship(back_populates="bill")


class Payment(Base):
    __tablename__ = "payment"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payment_amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bill.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True)  # idempotency key (Guide §5.3)
    amount: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bill: Mapped[Bill] = relationship(back_populates="payments")
