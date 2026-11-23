"""Exercise the tool through the real MCP protocol with an in-process MCP client."""

import pytest
from mcp import Client
from mcp.types import TextContent

from billing_docs.server import build_server

TOOL = "search_billing_documentation"
pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def server():
    return build_server()


async def test_tool_is_listed_with_schema(server):
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
    assert [t.name for t in tools] == [TOOL]
    schema = tools[0].input_schema
    assert schema["required"] == ["query"]
    assert schema["properties"]["top_k"]["maximum"] == 10
    assert tools[0].annotations is not None
    assert tools[0].annotations.read_only_hint is True


async def test_search_returns_guide_format(server):
    async with Client(server) as client:
        result = await client.call_tool(TOOL, {"query": "How much does extra internet cost?", "top_k": 2})
    assert result.is_error is False
    data = result.structured_content
    assert data["document"] == "Mobile_Provider_Billing_Guide.md"
    assert data["document_id"] == "MOB-BILLING-2026-01"
    assert [m["section"] for m in data["matches"]] == ["8.1", "3.2"]
    first = data["matches"][0]
    assert set(first) == {"section", "heading", "parent_heading", "text", "score"}
    assert "$10" in first["text"]


async def test_default_top_k_is_three(server):
    async with Client(server) as client:
        result = await client.call_tool(TOOL, {"query": "payment"})
    assert len(result.structured_content["matches"]) == 3


async def test_no_matches_is_not_an_error(server):
    async with Client(server) as client:
        result = await client.call_tool(TOOL, {"query": "weather in izmir"})
    assert result.is_error is False
    assert result.structured_content["matches"] == []


async def test_blank_query_is_tool_error(server):
    async with Client(server) as client:
        result = await client.call_tool(TOOL, {"query": "   "})
    assert result.is_error is True
    assert isinstance(result.content[0], TextContent)
    assert "query must not be blank" in result.content[0].text


@pytest.mark.parametrize("args", [{}, {"query": ""}, {"query": "fees", "top_k": 0}, {"query": "fees", "top_k": 11}])
async def test_invalid_arguments_rejected(server, args):
    async with Client(server) as client:
        result = await client.call_tool(TOOL, args)
    assert result.is_error is True
