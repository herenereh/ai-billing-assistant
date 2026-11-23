"""The agent loop: LLM chooses tools → agent executes them → LLM writes the answer.

The agent (not the LLM) executes every tool call, and owns the payment confirmation step.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from billing_agent.llm.base import AgentContext, LLMProvider, LLMUnavailable
from billing_agent.periods import default_period, period_label
from billing_agent.prompts import build_system_prompt
from billing_agent.tools import TOOL_SPECS, PendingPayment, ToolExecutor

MAX_TOOL_ROUNDS = 4
_YES = {"yes", "y", "confirm", "confirmed", "i confirm", "yes please", "yes pay", "evet", "onaylıyorum", "onayla"}
_NO = {"no", "n", "cancel", "stop", "don't", "dont", "hayır", "hayir", "iptal", "vazgeç", "vazgec"}


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s']", "", text.lower()).strip()


@dataclass
class TraceEntry:
    tool: str
    arguments: dict
    ok: bool
    summary: str


@dataclass
class AgentReply:
    text: str
    trace: list[TraceEntry] = field(default_factory=list)
    awaiting_confirmation: bool = False


class BillingAgent:
    def __init__(
        self,
        provider: LLMProvider,
        executor: ToolExecutor,
        *,
        today: Callable[[], date] = date.today,
    ):
        self.provider = provider
        self.executor = executor
        self._today = today
        self.messages: list[dict] = []
        self.pending_payment: PendingPayment | None = None

    @property
    def context(self) -> AgentContext:
        return AgentContext(subscriber_no=self.executor.subscriber_no, today=self._today())

    async def handle(self, user_text: str) -> AgentReply:
        notice = ""
        if self.pending_payment is not None:
            answer = _normalize(user_text)
            if answer in _YES:
                pending, self.pending_payment = self.pending_payment, None
                return await self._confirm(user_text, pending)
            pending, self.pending_payment = self.pending_payment, None
            if answer in _NO:
                return self._say(user_text, "OK, the payment was cancelled. Nothing was charged.")
            # Anything else is not consent (Billing Guide §5.2): drop the payment, then answer normally.
            notice = f"(The {period_label(pending.month, pending.year)} payment was not confirmed and has been cancelled.)\n"
        elif _normalize(user_text) in _YES | _NO:
            return self._say(user_text, "There is no pending payment to confirm. Say 'pay my bill' to start one.")

        self.messages.append({"role": "user", "content": user_text})
        ctx = self.context
        system = build_system_prompt(ctx, period_label(*default_period(ctx.today)))
        trace: list[TraceEntry] = []

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                response = await self.provider.complete(system, self.messages, TOOL_SPECS, ctx)
            except LLMUnavailable as exc:
                self.messages.pop()  # forget the unanswered user turn so history stays valid
                return AgentReply(notice + f"The assistant is unavailable right now ({exc}). Please try again.", trace)
            if not response.tool_calls:
                text = notice + (response.text or "Sorry, I don't have an answer for that.")
                self.messages.append({"role": "assistant", "content": text, "provider_raw": response.provider_raw})
                return AgentReply(text, trace)

            self.messages.append({"role": "assistant", "content": response.text, "tool_calls": response.tool_calls,
                                  "provider_raw": response.provider_raw})
            pending: PendingPayment | None = None
            # Every call gets a result (providers require it), then a prepared payment stops the loop.
            for call in response.tool_calls:
                if pending is not None and call.name == "pay_bill":
                    result = {"ok": False, "error": {"code": "ONE_PAYMENT_AT_A_TIME",
                                                     "message": "Only one payment can be prepared at a time."}}
                else:
                    outcome = await self.executor.execute(call.name, call.arguments)
                    result = outcome.result
                    pending = pending or outcome.pending_payment
                trace.append(TraceEntry(call.name, call.arguments, result.get("ok", False), _summarize(result)))
                self.messages.append({"role": "tool", "tool_call_id": call.id, "provider_call_id": call.provider_id,
                                      "name": call.name, "content": result})
            if pending is not None:
                self.pending_payment = pending
                text = notice + _confirmation_prompt(pending)
                self.messages.append({"role": "assistant", "content": text})
                return AgentReply(text, trace, awaiting_confirmation=True)

        text = notice + "Sorry, I couldn't complete that request. Please rephrase it."
        self.messages.append({"role": "assistant", "content": text})
        return AgentReply(text, trace)

    async def _confirm(self, user_text: str, pending: PendingPayment) -> AgentReply:
        result = await self.executor.confirm_payment(pending)
        trace = [TraceEntry("pay_bill", {"month": pending.month, "year": pending.year,
                                         "amount": float(pending.amount), "transactionId": pending.transaction_id},
                            result.get("ok", False), _summarize(result))]
        label = period_label(pending.month, pending.year)
        if result.get("ok"):
            text = (
                f"Payment successful: ${pending.amount:,.2f} paid for your {label} bill "
                f"(transaction {result['transactionId']}). Remaining balance: "
                f"${result['remainingBalance']:,.2f}, status {result['billStatus']}."
            )
        elif result["error"]["code"] == "SERVICE_UNAVAILABLE":
            text = (f"I couldn't reach the billing service, so I can't confirm whether the {label} payment "
                    "went through. Please check your bill before trying again.")
        else:
            text = f"The payment was not completed: {result['error']['message']}"
        reply = self._say(user_text, text)
        reply.trace = trace
        return reply

    def _say(self, user_text: str, text: str) -> AgentReply:
        self.messages.append({"role": "user", "content": user_text})
        self.messages.append({"role": "assistant", "content": text})
        return AgentReply(text)


def _confirmation_prompt(p: PendingPayment) -> str:
    return (
        "Please confirm this payment:\n"
        f"  Subscriber: {p.subscriber_no}\n"
        f"  Bill:       {period_label(p.month, p.year)}\n"
        f"  Amount:     ${p.amount:,.2f} (remaining balance ${p.remaining_before:,.2f})\n"
        "Reply 'yes' to pay or 'no' to cancel."
    )


def _summarize(result: dict) -> str:
    if not result.get("ok"):
        return f"error {result['error']['code']}"
    if "matches" in result:
        return "sections " + ", ".join(m["section"] for m in result["matches"]) if result["matches"] else "no matches"
    if "charges" in result:
        return f"total {result['charges']['total']}, {result['usage']['phoneMinutes']} min, {result['usage']['internetGb']} GB"
    if result.get("status") == "CONFIRMATION_REQUIRED":
        return f"awaiting confirmation for ${result['amount']}"
    if "paymentStatus" in result:
        return f"{result['paymentStatus']}, remaining {result['remainingBalance']}"
    if "total" in result:
        return f"total {result['total']}, remaining {result['remainingBalance']}, {result['status']}"
    return json.dumps(result)[:80]
