"""MCP server exposing `search_billing_documentation` over the Mobile Provider Billing Guide.

Run:
    uv run python -m billing_docs.server                     # streamable HTTP on 127.0.0.1:8001/mcp
    uv run python -m billing_docs.server --transport stdio   # stdio, for local MCP clients
    MCP_HOST=0.0.0.0 MCP_PORT=8000 uv run python -m billing_docs.server   # container / cloud
"""

from __future__ import annotations

import argparse
import os
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from billing_docs.indexer import GuideIndex

MAX_TOP_K = 10


class Match(BaseModel):
    section: str = Field(description="Section ID in the guide, e.g. '3.2'")
    heading: str = Field(description="Section heading")
    parent_heading: str = Field(description="Top-level section heading, e.g. 'Internet pricing'")
    text: str = Field(description="Section text (excerpt to quote or summarize)")
    score: float = Field(description="BM25 relevance score; higher is more relevant")


class SearchResult(BaseModel):
    document: str
    document_id: str
    query: str
    matches: list[Match]


def build_server(index: GuideIndex | None = None) -> MCPServer:
    index = index or GuideIndex.from_file()
    server = MCPServer(
        name="billing-docs",
        title="Mobile Provider Billing Guide",
        version="1.0.0",
        instructions=(
            "Search the mobile provider's billing policy guide (pricing, allowances, billing cycles, "
            "partial payments, late payments, disputes). It contains policy only, never live subscriber "
            "data: use the Billing REST API for actual bills, usage and payments."
        ),
    )

    @server.tool(
        name="search_billing_documentation",
        description=(
            "Full-text (BM25) search over Mobile_Provider_Billing_Guide.md. Returns the most relevant "
            "sections with section ID, heading, document ID and text. Use for billing rules and policy "
            "questions such as extra internet pricing, free minutes, partial payments, due dates, late "
            "payments and disputes."
        ),
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def search_billing_documentation(
        query: Annotated[str, Field(min_length=1, max_length=500, description="Natural-language question or keywords")],
        top_k: Annotated[int, Field(ge=1, le=MAX_TOP_K, description="Maximum number of sections to return")] = 3,
    ) -> SearchResult:
        if not query.strip():
            raise ToolError("query must not be blank")
        hits = index.search(query, top_k=top_k)
        return SearchResult(
            document=index.document_name,
            document_id=index.document_id,
            query=query,
            matches=[
                Match(
                    section=h.chunk.section,
                    heading=h.chunk.heading,
                    parent_heading=h.chunk.parent_heading,
                    text=h.chunk.text,
                    score=round(h.score, 3),
                )
                for h in hits
            ],
        )

    @server.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "document_id": index.document_id, "sections": len(index.chunks)})

    return server


def _transport_security(host: str) -> TransportSecuritySettings | None:
    """Localhost keeps the SDK's DNS-rebinding protection. In a container behind Azure ingress the
    public host name is not known in advance, so allowed hosts come from MCP_ALLOWED_HOSTS."""
    allowed = [h.strip() for h in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if allowed:
        return TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=allowed)
    if host in ("127.0.0.1", "localhost", "::1"):
        return None  # SDK default: localhost-only protection
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--transport", choices=["streamable-http", "stdio"], default="streamable-http")
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8001")))
    args = parser.parse_args()

    server = build_server()
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run(
            "streamable-http",
            host=args.host,
            port=args.port,
            stateless_http=True,   # no sticky sessions needed; scales to zero cleanly
            json_response=True,
            transport_security=_transport_security(args.host),
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMCP server stopped.")
