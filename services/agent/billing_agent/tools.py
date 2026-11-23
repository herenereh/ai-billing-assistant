"""Tools the agent can call, in a provider-neutral form (JSON Schema), and their execution.

Safety rules enforced here, in code, not left to the LLM:
- No tool accepts a subscriber number. Identity always comes from the logged-in session.
- `pay_bill` never pays. It only prepares a PendingPayment; the agent asks the user to confirm,
  and only an explicit "yes" executes it (Billing Guide §5.2).
- A payment is reported as successful only when the Pay Bill API confirms it (§5.3), and a
  retry after a network failure reuses the same transaction ID so it cannot pay twice.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from billing_agent.api_client import ApiError, ApiUnavailable, BillingApiClient
from billing_agent.docs_client import DocsClient, DocsError

_MONTH = {"type": "integer", "minimum": 1, "maximum": 12, "description": "Billing month, 1-12"}
_YEAR = {"type": "integer", "minimum": 2000, "maximum": 2100, "description": "Billing year, e.g. 2026"}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON Schema; adapters convert it to Claude/Gemini tool definitions


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="search_billing_documentation",
        description=(
            "Search the mobile provider's Billing Guide (MCP). Use for policy and pricing rules: "
            "allowances, extra internet/minute pricing, billing cycles, due dates, partial or late "
            "payments, disputes. Contains no subscriber data. Cite the returned section IDs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The policy question or keywords"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="query_bill",
        description=(
            "Get the logged-in subscriber's stored bill for a month: total, paid amount, remaining "
            "balance, status and due date. Use for 'what is my bill' questions."
        ),
        parameters={
            "type": "object",
            "properties": {"month": _MONTH, "year": _YEAR},
            "required": ["month", "year"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="query_bill_detailed",
        description=(
            "Get the logged-in subscriber's bill breakdown for a month: phone minutes, internet MB/GB, "
            "phone and internet charges and usage records. Use to explain why a bill is what it is."
        ),
        parameters={
            "type": "object",
            "properties": {"month": _MONTH, "year": _YEAR},
            "required": ["month", "year"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="pay_bill",
        description=(
            "Prepare a payment of the logged-in subscriber's bill. This does NOT pay: the user is asked "
            "to confirm first. Omit amount to pay the full remaining balance."
        ),
        parameters={
            "type": "object",
            "properties": {
                "month": _MONTH,
                "year": _YEAR,
                "amount": {"type": "number", "exclusiveMinimum": 0, "description": "Amount in USD (optional)"},
            },
            "required": ["month", "year"],
            "additionalProperties": False,
        },
    ),
]
TOOLS_BY_NAME = {t.name: t for t in TOOL_SPECS}


@dataclass(frozen=True)
class PendingPayment:
    subscriber_no: str
    month: int
    year: int
    amount: Decimal
    remaining_before: Decimal
    transaction_id: str = field(default_factory=lambda: f"agent-{uuid.uuid4().hex[:20]}")


@dataclass
class ToolOutcome:
    result: dict
    pending_payment: PendingPayment | None = None


def _error(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}}


def _require_period(args: dict) -> tuple[int, int]:
    month, year = args.get("month"), args.get("year")
    if not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("month must be an integer 1-12")
    if not isinstance(year, int) or not 2000 <= year <= 2100:
        raise ValueError("year must be an integer 2000-2100")
    return month, year


class ToolExecutor:
    def __init__(self, api: BillingApiClient, docs: DocsClient, subscriber_no: str):
        self.api = api
        self.docs = docs
        self.subscriber_no = subscriber_no  # from login only

    async def execute(self, name: str, args: dict[str, Any]) -> ToolOutcome:
        if name not in TOOLS_BY_NAME:
            return ToolOutcome(_error("UNKNOWN_TOOL", f"No tool named {name}"))
        try:
            if name == "search_billing_documentation":
                query = str(args.get("query", "")).strip()
                if not query:
                    raise ValueError("query must not be empty")
                return ToolOutcome({"ok": True, **await self.docs.search(query, int(args.get("top_k", 3)))})

            month, year = _require_period(args)
            if name == "query_bill":
                return ToolOutcome({"ok": True, **await self.api.query_bill(self.subscriber_no, month, year)})
            if name == "query_bill_detailed":
                return ToolOutcome({"ok": True, **await self.api.query_bill_detailed(month, year)})
            return await self._prepare_payment(month, year, args.get("amount"))
        except ValueError as exc:
            return ToolOutcome(_error("INVALID_ARGUMENTS", str(exc)))
        except ApiError as exc:
            return ToolOutcome(_error(exc.code, exc.message))
        except (ApiUnavailable, DocsError) as exc:
            return ToolOutcome(_error("SERVICE_UNAVAILABLE", str(exc)))

    async def _prepare_payment(self, month: int, year: int, raw_amount: Any) -> ToolOutcome:
        bill = await self.api.query_bill(self.subscriber_no, month, year)
        remaining = Decimal(str(bill["remainingBalance"])).quantize(Decimal("0.01"))
        if remaining <= 0:
            return ToolOutcome(_error("ALREADY_PAID", f"The {month:02d}/{year} bill is already fully paid."))
        if raw_amount is None:
            amount = remaining
        else:
            try:
                amount = Decimal(str(raw_amount))
            except InvalidOperation:
                raise ValueError("amount must be a number")
            if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
                raise ValueError("amount must be positive with at most 2 decimals")
            if amount > remaining:
                return ToolOutcome(_error(
                    "AMOUNT_TOO_HIGH", f"Amount ${amount} is more than the remaining balance ${remaining}."
                ))
        pending = PendingPayment(self.subscriber_no, month, year, amount, remaining)
        return ToolOutcome(
            {"ok": True, "status": "CONFIRMATION_REQUIRED", "subscriberNo": self.subscriber_no,
             "month": month, "year": year, "amount": float(amount), "remainingBalance": float(remaining)},
            pending_payment=pending,
        )

    async def confirm_payment(self, pending: PendingPayment) -> dict:
        """Execute a confirmed payment. One retry on network failure, with the same transaction ID."""
        for attempt in (1, 2):
            try:
                result = await self.api.pay_bill(pending.month, pending.year, pending.amount, pending.transaction_id)
                return {"ok": True, **result}
            except ApiUnavailable as exc:
                if attempt == 2:
                    return _error("SERVICE_UNAVAILABLE", f"Payment status unknown, service unreachable: {exc}")
            except ApiError as exc:
                if exc.code == "DUPLICATE_TRANSACTION" and attempt == 2:
                    # The first attempt reached the API before the connection dropped.
                    bill = await self.api.query_bill(self.subscriber_no, pending.month, pending.year)
                    return {"ok": True, "paymentStatus": "SUCCESS", "transactionId": pending.transaction_id,
                            "amount": float(pending.amount), "paidAmount": bill["paidAmount"],
                            "remainingBalance": bill["remainingBalance"], "billStatus": bill["status"],
                            "note": "recovered after a retry"}
                return _error(exc.code, exc.message)
        raise AssertionError("unreachable")
