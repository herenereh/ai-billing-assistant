"""Run the four assignment scenarios against running services and save a log for the README.

    AGENT_DEMO_PASSWORD=<seed password> uv run python -m billing_agent.demo --subscriber 5551001 \
        --out ../../docs/logs/agent_scenarios.md

Uses API_BASE_URL / MCP_URL from the environment or .env (local by default, Azure gateway later).
Note: the payment scenario really records a (simulated) payment.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

from billing_agent.agent import BillingAgent
from billing_agent.api_client import BillingApiClient
from billing_agent.cli import build_provider
from billing_agent.config import AgentSettings
from billing_agent.docs_client import DocsClient
from billing_agent.tools import ToolExecutor

SCENARIOS = [
    ("MCP only", ["How much does extra internet cost?"]),
    ("API only", ["What is my October bill?"]),
    ("API + MCP", ["Why is my October bill higher?"]),
    ("Payment with explicit confirmation", ["Pay my bill", "yes"]),
]


async def run(subscriber: str, password: str) -> list[str]:
    settings = AgentSettings()
    api = BillingApiClient(settings.api_base_url, subscription_key=settings.apim_subscription_key)
    provider = build_provider(settings)
    lines = [
        "# Agent scenarios",
        "",
        f"- Run at: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- LLM provider: `{provider.name}`",
        f"- Billing API: `{settings.api_base_url}`",
        f"- MCP server: `{settings.mcp_url}`",
        f"- Logged in as: `{subscriber}`",
        "",
    ]
    try:
        await api.login(subscriber, password)
        agent = BillingAgent(provider, ToolExecutor(api, DocsClient(settings.mcp_url), subscriber))
        for title, turns in SCENARIOS:
            lines += [f"## {title}", "", "```text"]
            for user_text in turns:
                reply = await agent.handle(user_text)
                lines.append(f"you> {user_text}")
                for t in reply.trace:
                    args = ", ".join(f"{k}={v}" for k, v in t.arguments.items())
                    lines.append(f"  [tool] {t.tool}({args}) -> {'ok' if t.ok else 'failed'}: {t.summary}")
                lines.append(f"assistant> {reply.text}")
                lines.append("")
            lines += ["```", ""]
    finally:
        await api.aclose()
    usage = getattr(provider, "usage", None)
    if usage is not None and usage.calls:
        lines += ["## LLM token usage", "",
                  f"{usage.calls} calls, {usage.prompt_tokens} input tokens, {usage.output_tokens} output tokens, "
                  f"{usage.thinking_tokens} thinking tokens.", ""]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscriber", default="5551001")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    password = os.environ.get("AGENT_DEMO_PASSWORD")
    if not password:
        raise SystemExit("Set AGENT_DEMO_PASSWORD to the subscriber's (test) password")
    lines = asyncio.run(run(args.subscriber, password))
    print("\n".join(lines))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
