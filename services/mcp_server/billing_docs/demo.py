"""Run the three required retrieval demonstrations against a running MCP server over HTTP.

    uv run python -m billing_docs.demo                                  # local server
    uv run python -m billing_docs.demo --url https://<app>/mcp --out ../../docs/logs/mcp_retrieval_demo.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp import Client

TOOL = "search_billing_documentation"
DEMO_QUERIES = [
    "How much does extra internet cost?",
    "Can I pay only part of my bill?",
    "What happens if I pay late?",
]


async def run(url: str) -> list[dict]:
    results = []
    async with Client(url) as client:
        tools = (await client.list_tools()).tools
        print(f"Connected to {url}; tools: {[t.name for t in tools]}\n")
        for query in DEMO_QUERIES:
            result = await client.call_tool(TOOL, {"query": query, "top_k": 3})
            data = result.structured_content
            results.append(data)
            print(f"Q: {query}")
            for m in data["matches"]:
                print(f"   §{m['section']:<4} {m['heading']:<40} score={m['score']}")
            print()
    return results


def to_markdown(url: str, results: list[dict]) -> str:
    lines = [
        "# MCP retrieval demo",
        "",
        f"- Server: `{url}`",
        f"- Tool: `{TOOL}`",
        "",
    ]
    for i, data in enumerate(results, 1):
        lines += [f"## Query {i}: “{data['query']}”", "", "| Rank | Section | Heading | Score |", "|---|---|---|---|"]
        lines += [
            f"| {r} | {m['section']} | {m['heading']} | {m['score']} |" for r, m in enumerate(data["matches"], 1)
        ]
        lines += ["", "<details><summary>Raw tool result</summary>", "", "```json",
                  json.dumps(data, indent=2, ensure_ascii=False), "```", "", "</details>", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001/mcp")
    parser.add_argument("--out", type=Path, help="Write a Markdown log of the results")
    args = parser.parse_args()
    results = asyncio.run(run(args.url))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(to_markdown(args.url, results), encoding="utf-8")
        print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
