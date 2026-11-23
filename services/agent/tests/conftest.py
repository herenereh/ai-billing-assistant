from datetime import date

import pytest

from billing_agent.agent import BillingAgent
from billing_agent.api_client import BillingApiClient
from billing_agent.llm.rule_based import RuleBasedProvider
from billing_agent.tools import ToolExecutor
from tests.fakes import FakeBillingApi, FakeDocs

TODAY = date(2026, 11, 22)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fake_api():
    return FakeBillingApi()


@pytest.fixture
def fake_docs():
    return FakeDocs()


@pytest.fixture
async def api(fake_api):
    client = BillingApiClient("http://gateway.test/api/v1", transport=fake_api.transport())
    yield client
    await client.aclose()


@pytest.fixture
async def agent(api, fake_docs):
    await api.login("5551001", "pw1")
    return BillingAgent(RuleBasedProvider(), ToolExecutor(api, fake_docs, "5551001"), today=lambda: TODAY)
