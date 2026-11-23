"""MCP client for the billing documentation server (search_billing_documentation)."""

from __future__ import annotations

from typing import Any

from mcp import Client
from mcp.types import TextContent

TOOL_NAME = "search_billing_documentation"


class DocsError(Exception):
    pass


class DocsClient:
    def __init__(self, server: Any):
        """`server` is an MCP URL (streamable HTTP) or, in tests, an in-process MCPServer."""
        self._server = server

    async def search(self, query: str, top_k: int = 3) -> dict:
        try:
            async with Client(self._server) as client:
                result = await client.call_tool(TOOL_NAME, {"query": query, "top_k": top_k})
        except Exception as exc:  # connection refused, timeouts, protocol errors
            raise DocsError(f"documentation service unavailable: {exc}") from exc
        if result.is_error:
            text = next((c.text for c in result.content if isinstance(c, TextContent)), "unknown error")
            raise DocsError(text)
        return result.structured_content
