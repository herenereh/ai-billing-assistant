"""Unit tests for the billing rules. Example values come straight from the Billing Guide."""

from datetime import date
from decimal import Decimal

import pytest

from app.services.billing_calc import (
    bill_status,
    calculate_bill,
    due_date,
    internet_charge,
    phone_charge,
    validate_payment,
    validate_period,
)

D = Decimal


# --- Phone (Guide §2) -------------------------------------------------------

@pytest.mark.parametrize(
    "minutes, expected",
    [
        (0, "0"),
        (1_000, "0"),        # §2.1 first 1,000 minutes free
        (1_001, "10"),       # §2.2 example
        (1_350, "10"),       # §4.3 worked example
        (2_000, "10"),
        (2_001, "20"),       # §2.2 example
        (10_000, "90"),
    ],
)
def test_phone_charge(minutes, expected):
    assert phone_charge(minutes) == D(expected)


# --- Internet (Guide §3) ----------------------------------------------------

@pytest.mark.parametrize(
    "megabytes, expected",
    [
        (0, "50"),           # §3.1 base applies even with zero usage
        (20_000, "50"),      # 20 GB → $50
        (20_001, "60"),      # just over 20 GB starts a new block
        (21_000, "60"),      # 21 GB → $60
        (30_000, "60"),      # 30 GB → $60
        (30_001, "70"),
        (35_000, "70"),      # 35 GB → $70
        (40_000, "70"),
    ],
)
def test_internet_charge(megabytes, expected):
    assert internet_charge(megabytes) == D(expected)


# --- Total (Guide §4) -------------------------------------------------------

def test_worked_example_total_is_80():
    bill = calculate_bill(phone_minutes=1_350, internet_mb=35_000)
    assert bill.phone_charge == D("10")
    assert bill.internet_charge == D("70")
    assert bill.total == D("80")
    assert bill.internet_gb == D("35")


def test_zero_usage_bill_is_internet_base_only():
    assert calculate_bill(0, 0).total == D("50")


@pytest.mark.parametrize("fn", [phone_charge, internet_charge])
def test_negative_usage_rejected(fn):
    with pytest.raises(ValueError):
        fn(-1)


@pytest.mark.parametrize("fn", [phone_charge, internet_charge])
@pytest.mark.parametrize("bad", [1.5, "100", True])
def test_non_integer_usage_rejected(fn, bad):
    with pytest.raises(TypeError):
        fn(bad)


# --- Billing period and due date (Guide §6.1) -------------------------------

def test_due_date_october_2026():
    assert due_date(2026, 10) == date(2026, 11, 15)


def test_due_date_crosses_year():
    assert due_date(2026, 12) == date(2027, 1, 15)


def test_due_date_leap_february():
    assert due_date(2028, 2) == date(2028, 3, 15)  # Feb 29 + 15 days


@pytest.mark.parametrize("year, month", [(2026, 0), (2026, 13), (1999, 5), (2101, 1)])
def test_invalid_period_rejected(year, month):
    with pytest.raises(ValueError):
        validate_period(year, month)


# --- Payment status and validation (Guide §5) -------------------------------

@pytest.mark.parametrize(
    "total, paid, expected",
    [
        ("80", "0", "UNPAID"),
        ("80", "30", "PARTIAL"),   # §5.1 partial payment does not mark paid
        ("80", "79.99", "PARTIAL"),
        ("80", "80", "PAID"),
    ],
)
def test_bill_status(total, paid, expected):
    assert bill_status(D(total), D(paid)) == expected


def test_valid_partial_and_full_payment():
    validate_payment(D("30"), total=D("80"), paid_amount=D("0"))
    validate_payment(D("50"), total=D("80"), paid_amount=D("30"))


@pytest.mark.parametrize(
    "amount, paid, message",
    [
        ("0", "0", "greater than zero"),
        ("-5", "0", "greater than zero"),
        ("10.001", "0", "2 decimal places"),
        ("80.01", "0", "exceeds remaining"),
        ("60", "30", "exceeds remaining"),
        ("1", "80", "already fully paid"),
        ("NaN", "0", "finite"),
        ("Infinity", "0", "finite"),
    ],
)
def test_invalid_payment_rejected(amount, paid, message):
    with pytest.raises(ValueError, match=message):
        validate_payment(D(amount), total=D("80"), paid_amount=D(paid))
