"""Pure billing rules from Mobile_Provider_Billing_Guide.md (MOB-BILLING-2026-01).

Everything here is side-effect free so it can be unit tested exhaustively.
Money is returned as Decimal (never float). Usage is integer minutes / MB.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

# Guide §2: phone pricing
FREE_MINUTES = 1_000
PHONE_BLOCK_MINUTES = 1_000
PHONE_BLOCK_PRICE = Decimal("10.00")

# Guide §3: internet pricing (1 GB = 1,000 MB, §3.3)
MB_PER_GB = 1_000
INTERNET_BASE_PRICE = Decimal("50.00")
INTERNET_INCLUDED_MB = 20 * MB_PER_GB
INTERNET_BLOCK_MB = 10 * MB_PER_GB
INTERNET_BLOCK_PRICE = Decimal("10.00")

# Guide §2.3 / §3.3: fixed amount recorded per Add Usage event
PHONE_MINUTES_PER_EVENT = 10
INTERNET_MB_PER_EVENT = 1

# Guide §6.1: due 15 calendar days after the end of the billing month
DUE_DAYS_AFTER_PERIOD_END = 15

STATUS_UNPAID = "UNPAID"
STATUS_PARTIAL = "PARTIAL"
STATUS_PAID = "PAID"


def _ceil_div(numerator: int, denominator: int) -> int:
    """Integer ceiling division for non-negative numerators (no float rounding)."""
    return -(-numerator // denominator)


def _check_non_negative(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def phone_charge(minutes: int) -> Decimal:
    """$10 × ceil(max(0, minutes − 1000) / 1000)  (Guide §4.2)."""
    _check_non_negative(minutes, "minutes")
    extra_blocks = _ceil_div(max(0, minutes - FREE_MINUTES), PHONE_BLOCK_MINUTES)
    return PHONE_BLOCK_PRICE * extra_blocks


def internet_charge(megabytes: int) -> Decimal:
    """$50 + $10 × ceil(max(0, GB − 20) / 10), with GB = MB / 1000  (Guide §4.2).

    Computed in MB so partial GB are handled exactly: 20,001 MB is over 20 GB.
    The $50 base applies even with zero usage (Guide §3.1).
    """
    _check_non_negative(megabytes, "megabytes")
    extra_blocks = _ceil_div(max(0, megabytes - INTERNET_INCLUDED_MB), INTERNET_BLOCK_MB)
    return INTERNET_BASE_PRICE + INTERNET_BLOCK_PRICE * extra_blocks


@dataclass(frozen=True)
class BillBreakdown:
    phone_minutes: int
    internet_mb: int
    phone_charge: Decimal
    internet_charge: Decimal

    @property
    def total(self) -> Decimal:
        return self.phone_charge + self.internet_charge

    @property
    def internet_gb(self) -> Decimal:
        return Decimal(self.internet_mb) / MB_PER_GB


def calculate_bill(phone_minutes: int, internet_mb: int) -> BillBreakdown:
    """Total = phone + internet; no taxes, fees or discounts (Guide §4.2)."""
    return BillBreakdown(
        phone_minutes=phone_minutes,
        internet_mb=internet_mb,
        phone_charge=phone_charge(phone_minutes),
        internet_charge=internet_charge(internet_mb),
    )


def validate_period(year: int, month: int) -> None:
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    if not 2000 <= year <= 2100:
        raise ValueError("year must be between 2000 and 2100")


def due_date(year: int, month: int) -> date:
    """Last day of the billing month + 15 days (Guide §6.1: Oct 2026 → 2026-11-15)."""
    validate_period(year, month)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day) + timedelta(days=DUE_DAYS_AFTER_PERIOD_END)


def bill_status(total: Decimal, paid_amount: Decimal) -> str:
    """UNPAID → PARTIAL → PAID (Guide §5.1: a partial payment does not mark it paid)."""
    if paid_amount <= 0:
        return STATUS_UNPAID
    if paid_amount < total:
        return STATUS_PARTIAL
    return STATUS_PAID


def validate_payment(amount: Decimal, total: Decimal, paid_amount: Decimal) -> None:
    """Reject non-positive amounts, sub-cent precision and overpayment."""
    if not amount.is_finite():
        raise ValueError("payment amount must be a finite number")
    if amount <= 0:
        raise ValueError("payment amount must be greater than zero")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("payment amount must have at most 2 decimal places")
    remaining = total - paid_amount
    if remaining <= 0:
        raise ValueError("bill is already fully paid")
    if amount > remaining:
        raise ValueError(f"payment amount exceeds remaining balance of {remaining}")
