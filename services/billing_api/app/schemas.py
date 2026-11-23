"""Request/response models. JSON uses camelCase; money is serialized as a JSON number."""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from pydantic.alias_generators import to_camel

def _money_json(value: Decimal) -> float:
    return float(value)


Money = Annotated[Decimal, PlainSerializer(_money_json, when_used="json")]
Month = Annotated[int, Field(ge=1, le=12, examples=[10])]
Year = Annotated[int, Field(ge=2000, le=2100, examples=[2026])]
SubscriberNo = Annotated[str, Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9]+$", examples=["5551001"])]


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UsageType(str, Enum):
    PHONE = "PHONE"
    INTERNET = "INTERNET"


# --- Auth -------------------------------------------------------------------

class LoginRequest(ApiModel):
    subscriber_no: SubscriberNo
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


# --- Usage ------------------------------------------------------------------

class AddUsageRequest(ApiModel):
    subscriber_no: SubscriberNo
    month: Month
    year: Year
    usage_type: UsageType
    count: int = Field(
        default=1,
        ge=1,
        le=100_000,
        description="Number of usage events to record (default 1). Each PHONE event = 10 minutes, "
        "each INTERNET event = 1 MB (Billing Guide §2.3, §3.3).",
    )


class AddUsageResponse(ApiModel):
    transaction_status: str = "SUCCESS"
    subscriber_no: str
    month: int
    year: int
    usage_type: UsageType
    events: int
    quantity: int
    unit: str


# --- Bills ------------------------------------------------------------------

class CalculateBillRequest(ApiModel):
    subscriber_no: SubscriberNo
    month: Month
    year: Year


class BillSummary(ApiModel):
    subscriber_no: str
    month: int
    year: int
    total: Money
    paid_amount: Money
    remaining_balance: Money
    status: str
    due_date: date


class CalculateBillResponse(ApiModel):
    transaction_status: str = "SUCCESS"
    bill: BillSummary


class UsageTotals(ApiModel):
    phone_minutes: int
    internet_mb: int
    internet_gb: float


class ChargeBreakdown(ApiModel):
    phone_charge: Money
    internet_charge: Money
    total: Money


class UsageRecordOut(ApiModel):
    id: int
    usage_type: UsageType
    events: int
    quantity: int
    unit: str
    recorded_at: str


T = TypeVar("T")


class Page(ApiModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class BillDetailed(BillSummary):
    usage: UsageTotals
    charges: ChargeBreakdown
    usage_records: Page[UsageRecordOut]


# --- Payments ---------------------------------------------------------------

class PayBillRequest(ApiModel):
    month: Month
    year: Year
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2, examples=[30.00])
    transaction_id: str = Field(min_length=6, max_length=64, pattern=r"^[A-Za-z0-9_-]+$", examples=["tx-20261122-0001"])


class PayBillResponse(ApiModel):
    payment_status: str = "SUCCESS"
    transaction_id: str
    amount: Money
    paid_amount: Money
    remaining_balance: Money
    bill_status: str
