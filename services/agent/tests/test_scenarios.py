"""The assignment's example conversations: MCP-only, API-only, combined, and confirmed payment."""

import pytest

pytestmark = pytest.mark.anyio


def tools_used(reply):
    return [t.tool for t in reply.trace]


async def test_mcp_only_extra_internet_cost(agent, fake_api, fake_docs):
    reply = await agent.handle("How much does extra internet cost?")
    assert tools_used(reply) == ["search_billing_documentation"]
    assert fake_docs.queries == ["How much does extra internet cost?"]
    assert "§8.1" in reply.text and "$10" in reply.text
    assert all(r.url.path == "/api/v1/auth/login" for r in fake_api.requests)  # no billing API calls


async def test_api_only_october_bill(agent, fake_docs):
    reply = await agent.handle("What is my October bill?")
    assert tools_used(reply) == ["query_bill"]
    assert reply.trace[0].arguments == {"month": 10, "year": 2026}
    assert fake_docs.queries == []
    assert reply.text == ("Your October 2026 bill is $80.00. Paid: $0.00, remaining: $80.00 "
                          "(status UNPAID). Due date: 2026-11-15.")


async def test_combined_why_is_october_higher(agent, fake_docs):
    reply = await agent.handle("Why is my October bill higher?")
    assert tools_used(reply) == ["query_bill_detailed", "query_bill_detailed", "search_billing_documentation"]
    assert [t.arguments for t in reply.trace[:2]] == [{"month": 10, "year": 2026}, {"month": 9, "year": 2026}]
    text = reply.text
    assert "$80.00" in text and "1,350 minutes" in text and "35 GB" in text      # numbers from the API
    assert "$30.00 more than September 2026" in text                            # compared with previous month
    assert "§3.2" in text and "§2.2" in text                                    # rules cited from the guide
    assert "15 GB over 20 GB" in text


async def test_pay_bill_requires_explicit_confirmation(agent, fake_api):
    reply = await agent.handle("Pay my bill")
    assert reply.awaiting_confirmation
    assert "Subscriber: 5551001" in reply.text
    assert "Bill:       October 2026" in reply.text
    assert "Amount:     $80.00" in reply.text
    assert fake_api.payment_requests() == []  # nothing paid yet

    done = await agent.handle("yes")
    payments = fake_api.payment_requests()
    assert len(payments) == 1
    assert payments[0]["amount"] == 80.0
    assert payments[0]["transactionId"].startswith("agent-")
    assert done.text.startswith("Payment successful: $80.00 paid for your October 2026 bill")
    assert "status PAID" in done.text
    assert agent.pending_payment is None


async def test_turkish_conversation_routes_the_same(agent, fake_docs):
    bill = await agent.handle("Ekim faturam ne kadar?")
    assert tools_used(bill) == ["query_bill"]
    assert bill.trace[0].arguments == {"month": 10, "year": 2026}
    pay = await agent.handle("Faturamı öde")
    assert pay.awaiting_confirmation
    done = await agent.handle("evet")
    assert done.text.startswith("Payment successful")
