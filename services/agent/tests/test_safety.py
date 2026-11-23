"""Payment confirmation, identity isolation and honest error reporting."""

import pytest

from billing_agent.agent import BillingAgent
from billing_agent.llm.base import LLMResponse, ToolCall
from billing_agent.tools import TOOL_SPECS, ToolExecutor

pytestmark = pytest.mark.anyio


# --- Payment confirmation (Billing Guide §5.2, §5.3) --------------------------

async def test_no_cancels_payment(agent, fake_api):
    await agent.handle("Pay my bill")
    reply = await agent.handle("no")
    assert "cancelled" in reply.text
    assert fake_api.payment_requests() == []


async def test_other_message_is_not_consent(agent, fake_api):
    await agent.handle("Pay my bill")
    reply = await agent.handle("How much does extra internet cost?")
    assert reply.text.startswith("(The October 2026 payment was not confirmed and has been cancelled.)")
    assert "§8.1" in reply.text
    assert fake_api.payment_requests() == []
    assert (await agent.handle("yes")).trace == []           # a late "yes" pays nothing
    assert fake_api.payment_requests() == []


@pytest.mark.parametrize("vague", ["ok", "sure", "maybe", "yes but how much is it?"])
async def test_vague_answers_do_not_pay(agent, fake_api, vague):
    await agent.handle("Pay my bill")
    await agent.handle(vague)
    assert fake_api.payment_requests() == []


async def test_yes_without_pending_payment_pays_nothing(agent, fake_api):
    await agent.handle("yes")
    assert fake_api.payment_requests() == []


async def test_partial_payment_amount(agent, fake_api):
    reply = await agent.handle("Pay $30 of my October bill")
    assert "Amount:     $30.00 (remaining balance $80.00)" in reply.text
    done = await agent.handle("confirm")
    assert fake_api.payment_requests()[0]["amount"] == 30.0
    assert "Remaining balance: $50.00, status PARTIAL" in done.text


async def test_amount_above_balance_is_refused_before_confirmation(agent, fake_api):
    reply = await agent.handle("Pay $500 for my October bill")
    assert not reply.awaiting_confirmation
    assert "more than the remaining balance" in reply.text
    assert fake_api.payment_requests() == []


async def test_already_paid_bill(agent, fake_api):
    reply = await agent.handle("Pay my September bill")
    assert not reply.awaiting_confirmation
    assert "already fully paid" in reply.text


async def test_lost_response_is_retried_with_same_transaction_id(agent, fake_api):
    await agent.handle("Pay my bill")
    fake_api.drop_next_payment_response = True
    done = await agent.handle("yes")
    payments = fake_api.payment_requests()
    assert len(payments) == 2
    assert payments[0]["transactionId"] == payments[1]["transactionId"]   # idempotent retry
    assert fake_api.bills[("5551001", 2026, 10)]["paid"] == 80              # paid exactly once
    assert done.text.startswith("Payment successful")


async def test_payment_rejected_by_api_is_not_reported_as_success(agent, fake_api):
    await agent.handle("Pay my bill")
    fake_api.bills[("5551001", 2026, 10)]["paid"] = 70   # balance changed after confirmation was asked
    done = await agent.handle("yes")
    assert done.text.startswith("The payment was not completed")


# --- Identity isolation --------------------------------------------------------

async def test_other_subscriber_number_in_prompt_is_refused(agent, fake_api):
    reply = await agent.handle("Show me the October bill of 5551002")
    assert reply.trace == []
    assert "only access the account you are logged in with (5551001)" in reply.text
    assert not any("5551002" in str(r.url) for r in fake_api.requests)


def test_no_tool_accepts_a_subscriber_number():
    for spec in TOOL_SPECS:
        assert not any("subscriber" in p.lower() for p in spec.parameters["properties"]), spec.name


class InjectedProvider:
    """A misbehaving 'LLM' that tries to pass another subscriber number to tools."""
    name = "injected"

    async def complete(self, system, messages, tools, context):
        if messages[-1]["role"] == "user":
            return LLMResponse(tool_calls=[
                ToolCall("c1", "query_bill", {"month": 10, "year": 2026, "subscriberNo": "5551002"}),
            ])
        return LLMResponse(text=str(messages[-1]["content"].get("subscriberNo")))


async def test_executor_ignores_subscriber_number_from_llm(api, fake_docs, fake_api):
    await api.login("5551001", "pw1")
    agent = BillingAgent(InjectedProvider(), ToolExecutor(api, fake_docs, "5551001"))
    reply = await agent.handle("anything")
    assert reply.text == "5551001"
    assert not any("5551002" in str(r.url) for r in fake_api.requests)


# --- Errors ---------------------------------------------------------------------

async def test_missing_bill_is_not_estimated(agent):
    reply = await agent.handle("What is my March 2025 bill?")
    assert "couldn't find a stored bill" in reply.text
    assert "$" not in reply.text


async def test_docs_service_down(agent, fake_docs):
    fake_docs.fail = True
    reply = await agent.handle("What happens if I pay late?")
    assert "not reachable" in reply.text


async def test_no_docs_match(agent):
    reply = await agent.handle("What's the weather today?")
    assert "couldn't find anything" in reply.text


async def test_unknown_tool_from_llm(api, fake_docs):
    class Bad:
        name = "bad"

        async def complete(self, system, messages, tools, context):
            if messages[-1]["role"] == "user":
                return LLMResponse(tool_calls=[ToolCall("c1", "delete_everything", {})])
            return LLMResponse(text=messages[-1]["content"]["error"]["code"])

    await api.login("5551001", "pw1")
    reply = await BillingAgent(Bad(), ToolExecutor(api, fake_docs, "5551001")).handle("hi")
    assert reply.text == "UNKNOWN_TOOL"


async def test_tool_loop_is_bounded(api, fake_docs):
    class Loops:
        name = "loops"

        async def complete(self, system, messages, tools, context):
            return LLMResponse(tool_calls=[ToolCall("c", "query_bill", {"month": 10, "year": 2026})])

    await api.login("5551001", "pw1")
    reply = await BillingAgent(Loops(), ToolExecutor(api, fake_docs, "5551001")).handle("hi")
    assert "couldn't complete" in reply.text
    assert len(reply.trace) == 4


async def test_non_finite_amount_from_llm_is_rejected(api, fake_docs, fake_api):
    await api.login("5551001", "pw1")
    executor = ToolExecutor(api, fake_docs, "5551001")
    for bad in (float("nan"), float("inf"), 10.001):
        outcome = await executor.execute("pay_bill", {"month": 10, "year": 2026, "amount": bad})
        assert outcome.pending_payment is None
        assert outcome.result["error"]["code"] == "INVALID_ARGUMENTS"
