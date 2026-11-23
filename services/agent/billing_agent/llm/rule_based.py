"""Deterministic stand-in for an LLM: keyword routing to tools, templated answers from tool results.

It plays the same role a real LLM plays in the agent loop (first call: choose tools; second call:
write the answer from tool results), so the loop, tools and safety rules are exercised without
any LLM cost. Answers are in English.
"""

from __future__ import annotations

import itertools
import re
from decimal import Decimal

from billing_agent.llm.base import AgentContext, LLMResponse, ToolCall
from billing_agent.periods import default_period, parse_period, period_label, previous_period
from billing_agent.tools import ToolSpec

_POLICY_STARTS = (
    "can i", "could i", "is it possible", "what happens", "what if", "is there", "are there",
    "do i have to", "how do i", "how can i", "how does", "how do", "when is", "when are", "when do",
    "what is the", "what are the", "how much does", "how much do", "nasıl", "ne olur",
)
_PAY = re.compile(
    r"^\s*(please\s+)?pay\b|\bpay\s+(my|the|it|this|that|for)\b|\bi\s+want\s+to\s+pay\b"
    r"|faturamı\s+öde|\böde\b|ödemek\s+istiyorum|ödeme\s+yap"
)
_WHY = re.compile(r"\bwhy\b|\bneden\b|\bniye\b|\bhigher\b|\bexpensive\b|yüksek|\bexplain\b|açıkla")
_PERSONAL = re.compile(r"\bmy\b|\bmine\b|\bme\b|faturam|benim")
_BILL = re.compile(r"\bbill|\binvoice|fatura")
_DETAIL = re.compile(r"\bdetail|\bbreakdown\b|\busage\b|\bused\b|\bminutes\b|kullanım|detay")
_AMOUNT = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s?(?:\$|usd\b|dollars?\b|dolar\b)")
_SUBSCRIBER_NO = re.compile(r"\b\d{7,12}\b")

_ids = itertools.count(1)


def _call(name: str, **arguments) -> ToolCall:
    return ToolCall(id=f"call_{next(_ids)}", name=name, arguments=arguments)


def _money(value) -> str:
    return f"${Decimal(str(value)):,.2f}"


class RuleBasedProvider:
    name = "rule-based"

    async def complete(
        self, system: str, messages: list[dict], tools: list[ToolSpec], context: AgentContext
    ) -> LLMResponse:
        last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
        text = messages[last_user]["content"]
        results = {m["name"]: [] for m in messages[last_user:] if m["role"] == "tool"}
        for m in messages[last_user:]:
            if m["role"] == "tool":
                results[m["name"]].append(m["content"])
        if not results:
            return self._plan(text, context)
        return LLMResponse(text=self._answer(text, results, context))

    # --- step 1: choose tools -------------------------------------------------

    def _plan(self, text: str, ctx: AgentContext) -> LLMResponse:
        lower = text.lower().strip()
        others = [n for n in _SUBSCRIBER_NO.findall(lower) if n != ctx.subscriber_no]
        if others:
            return LLMResponse(text=(
                f"I can only access the account you are logged in with ({ctx.subscriber_no}). "
                "I can't look up or act on other subscribers' bills."
            ))

        period = parse_period(text, ctx.today)
        month, year = period or default_period(ctx.today)
        is_policy_question = lower.startswith(_POLICY_STARTS)

        if _PAY.search(lower) and not is_policy_question:
            args: dict[str, int | float] = {"month": month, "year": year}
            if amount := _AMOUNT.search(lower):
                args["amount"] = float(amount.group(1) or amount.group(2))
            return LLMResponse(tool_calls=[_call("pay_bill", **args)])

        personal_bill = bool(_PERSONAL.search(lower)) and bool(_BILL.search(lower) or _DETAIL.search(lower))
        if personal_bill and _WHY.search(lower):
            prev_m, prev_y = previous_period(month, year)
            return LLMResponse(tool_calls=[
                _call("query_bill_detailed", month=month, year=year),
                _call("query_bill_detailed", month=prev_m, year=prev_y),
                _call("search_billing_documentation",
                      query="additional internet blocks additional minutes pricing bill higher", top_k=4),
            ])
        if personal_bill and not is_policy_question:
            if _DETAIL.search(lower):
                return LLMResponse(tool_calls=[_call("query_bill_detailed", month=month, year=year)])
            return LLMResponse(tool_calls=[_call("query_bill", month=month, year=year)])
        return LLMResponse(tool_calls=[_call("search_billing_documentation", query=text, top_k=3)])

    # --- step 2: write the answer from tool results ----------------------------

    def _answer(self, text: str, results: dict[str, list[dict]], ctx: AgentContext) -> str:
        if "pay_bill" in results:  # only reached when preparing the payment failed
            r = results["pay_bill"][0]
            return r["error"]["message"] if r["error"]["code"] in ("ALREADY_PAID", "AMOUNT_TOO_HIGH") \
                else self._error_text(r)
        if "query_bill_detailed" in results and "search_billing_documentation" in results:
            return self._explain_bill(results["query_bill_detailed"], results["search_billing_documentation"][0])
        if "query_bill_detailed" in results:
            return self._detailed(results["query_bill_detailed"][0])
        if "query_bill" in results:
            return self._bill(results["query_bill"][0])
        return self._docs(results["search_billing_documentation"][0])

    @staticmethod
    def _error_text(result: dict) -> str:
        code, message = result["error"]["code"], result["error"]["message"]
        if code in ("BILL_NOT_FOUND",):
            return ("I couldn't find a stored bill for that month. It may not have been calculated yet, "
                    "so I can't give you a confirmed amount.")
        if code == "SERVICE_UNAVAILABLE":
            return "The billing service is not reachable right now. Please try again in a moment."
        if code in ("UNAUTHORIZED", "NOT_LOGGED_IN"):
            return "Your session has expired. Please log in again with /login."
        return f"Sorry, that didn't work: {message}"

    def _bill(self, r: dict) -> str:
        if not r["ok"]:
            return self._error_text(r)
        return (
            f"Your {period_label(r['month'], r['year'])} bill is {_money(r['total'])}. "
            f"Paid: {_money(r['paidAmount'])}, remaining: {_money(r['remainingBalance'])} "
            f"(status {r['status']}). Due date: {r['dueDate']}."
        )

    def _detailed(self, r: dict) -> str:
        if not r["ok"]:
            return self._error_text(r)
        u, c = r["usage"], r["charges"]
        return (
            f"{period_label(r['month'], r['year'])}: {u['phoneMinutes']:,} phone minutes and "
            f"{u['internetGb']:g} GB internet ({u['internetMb']:,} MB). Charges: phone {_money(c['phoneCharge'])}, "
            f"internet {_money(c['internetCharge'])}, total {_money(c['total'])}. "
            f"Remaining balance: {_money(r['remainingBalance'])} (status {r['status']})."
        )

    def _explain_bill(self, detailed: list[dict], docs: dict) -> str:
        current = detailed[0]
        if not current["ok"]:
            return self._error_text(current)
        cited = {m["section"] for m in docs.get("matches", [])} if docs.get("ok") else set()
        ref = lambda s: f" (Billing Guide §{s})" if s in cited else ""  # noqa: E731

        u, c = current["usage"], current["charges"]
        label = period_label(current["month"], current["year"])
        lines = [
            f"Your {label} bill is {_money(c['total'])}: phone {_money(c['phoneCharge'])} for "
            f"{u['phoneMinutes']:,} minutes and internet {_money(c['internetCharge'])} for {u['internetGb']:g} GB."
        ]
        previous = detailed[1] if len(detailed) > 1 and detailed[1]["ok"] else None
        if previous:
            pu, diff = previous["usage"], Decimal(str(c["total"])) - Decimal(str(previous["charges"]["total"]))
            change = "more" if diff > 0 else "less" if diff < 0 else "the same as"
            amount = f"{_money(abs(diff))} " if diff else ""
            lines.append(
                f"That is {amount}{change} than {period_label(previous['month'], previous['year'])} "
                f"({_money(previous['charges']['total'])}: {pu['phoneMinutes']:,} minutes, {pu['internetGb']:g} GB)."
            )
        if u["phoneMinutes"] > 1000:
            lines.append(
                f"Phone: the first 1,000 minutes are free and each started extra 1,000-minute block costs $10"
                f"{ref('2.2')}. You used {u['phoneMinutes'] - 1000:,} minutes over the free allowance."
            )
        else:
            lines.append(f"Phone: you stayed within the 1,000 free minutes{ref('2.1')}, so phone cost $0.")
        if u["internetMb"] > 20_000:
            over_gb = (u["internetMb"] - 20_000) / 1000
            lines.append(
                f"Internet: $50 covers up to 20 GB and each started extra 10 GB block costs $10{ref('3.2')}. "
                f"You were {over_gb:g} GB over 20 GB, which is why internet cost {_money(c['internetCharge'])}."
            )
        else:
            lines.append(f"Internet: you stayed within the 20 GB included in the $50 plan{ref('3.1')}.")
        return "\n".join(lines)

    def _docs(self, r: dict) -> str:
        if not r["ok"]:
            return self._error_text(r)
        matches = r.get("matches", [])
        if not matches:
            return "I couldn't find anything about that in the billing guide."
        top = matches[:2]
        body = "\n".join(f"• §{m['section']} {m['heading']}: {m['text']}" for m in top)
        return f"From the Billing Guide ({r['document_id']}):\n{body}"
