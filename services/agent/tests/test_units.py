"""Period parsing, API client behaviour and the system prompt."""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from billing_agent.api_client import ApiError, ApiUnavailable, BillingApiClient
from billing_agent.llm.base import AgentContext
from billing_agent.periods import default_period, parse_period
from billing_agent.prompts import build_system_prompt

TODAY = date(2026, 11, 22)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("What is my October bill?", (10, 2026)),
        ("my oct bill", (10, 2026)),
        ("bill for December", (12, 2025)),          # future month → last year
        ("April 2025 bill", (4, 2025)),
        ("my bill in may", (5, 2026)),
        ("May I pay part of my bill?", None),        # 'may' as a verb is not a month
        ("this month", (11, 2026)),
        ("last month's bill", (10, 2026)),
        ("Ekim faturam ne kadar?", (10, 2026)),
        ("ekimdeki fatura", (10, 2026)),
        ("Eylül 2026 faturası", (9, 2026)),
        ("geçen ay", (10, 2026)),
        ("Pay my bill", None),
    ],
)
def test_parse_period(text, expected):
    assert parse_period(text, TODAY) == expected


def test_default_period_is_last_finished_month():
    assert default_period(TODAY) == (10, 2026)
    assert default_period(date(2027, 1, 5)) == (12, 2026)


def test_system_prompt_pins_identity_and_date():
    prompt = build_system_prompt(AgentContext("5551001", TODAY), "October 2026")
    assert "The logged-in subscriber is 5551001" in prompt
    assert "Today is 2026-11-22" in prompt


pytestmark_anyio = pytest.mark.anyio


@pytest.mark.anyio
async def test_client_sends_bearer_and_gateway_key(fake_api):
    client = BillingApiClient("http://gw.test/api/v1", subscription_key="k-123", transport=fake_api.transport())
    await client.login("5551001", "pw1")
    await client.query_bill_detailed(10, 2026)
    detailed = fake_api.requests[-1]
    assert detailed.headers["Authorization"] == "Bearer tok-5551001"
    assert detailed.headers["Ocp-Apim-Subscription-Key"] == "k-123"
    assert str(detailed.url).startswith("http://gw.test/api/v1/bills/detailed?month=10&year=2026")
    await client.aclose()


@pytest.mark.anyio
async def test_client_raises_api_error_with_code(fake_api):
    client = BillingApiClient("http://gw.test/api/v1", transport=fake_api.transport())
    with pytest.raises(ApiError) as exc:
        await client.login("5551001", "wrong")
    assert (exc.value.status, exc.value.code) == (401, "INVALID_CREDENTIALS")
    await client.aclose()


@pytest.mark.anyio
async def test_protected_call_without_login_fails_locally(fake_api):
    client = BillingApiClient("http://gw.test/api/v1", transport=fake_api.transport())
    with pytest.raises(ApiError) as exc:
        await client.pay_bill(10, 2026, Decimal("10"), "tx-123456")
    assert exc.value.code == "NOT_LOGGED_IN"
    assert fake_api.requests == []
    await client.aclose()


@pytest.mark.anyio
async def test_network_error_is_api_unavailable():
    def boom(request):
        raise httpx.ConnectError("refused", request=request)

    client = BillingApiClient("http://gw.test/api/v1", transport=httpx.MockTransport(boom))
    with pytest.raises(ApiUnavailable):
        await client.query_bill("5551001", 10, 2026)
    await client.aclose()


@pytest.mark.anyio
async def test_non_json_error_body():
    client = BillingApiClient(
        "http://gw.test/api/v1", transport=httpx.MockTransport(lambda r: httpx.Response(502, text="Bad Gateway"))
    )
    with pytest.raises(ApiError) as exc:
        await client.query_bill("5551001", 10, 2026)
    assert (exc.value.status, exc.value.code) == (502, "HTTP_ERROR")
    await client.aclose()
