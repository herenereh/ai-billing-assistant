"""Command-line chat for the billing assistant.

    uv run python -m billing_agent.cli
    > /login 5551001
    > What is my October bill?

Commands: /login <subscriberNo>, /logout, /trace (toggle tool-call display), /help, /quit
"""

from __future__ import annotations

import argparse
import asyncio
import getpass

from billing_agent.agent import BillingAgent, trace_label
from billing_agent.api_client import ApiError, ApiUnavailable, BillingApiClient
from billing_agent.config import AgentSettings
from billing_agent.docs_client import DocsClient
from billing_agent.llm.rule_based import RuleBasedProvider
from billing_agent.tools import ToolExecutor

HELP = """Commands:
  /login <subscriberNo>   log in (password is asked without echo)
  /logout                 log out
  /trace                  show/hide the tool calls the agent makes
  /help                   this help
  /quit                   exit
Try: "How much does extra internet cost?", "What is my October bill?",
     "Why is my October bill higher?", "Pay my bill"."""


def build_provider(settings: AgentSettings):
    if settings.llm_provider == "rule-based":
        return RuleBasedProvider()
    if settings.llm_provider == "gemini":
        if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
            raise SystemExit("LLM_PROVIDER=gemini needs GEMINI_API_KEY in services/agent/.env")
        from billing_agent.llm.gemini import GeminiProvider

        return GeminiProvider(settings.gemini_api_key.get_secret_value(), settings.gemini_model)
    raise SystemExit(f"Unknown LLM_PROVIDER '{settings.llm_provider}'. Use 'rule-based' or 'gemini'.")


async def _read(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def main_async(show_trace: bool) -> None:
    settings = AgentSettings()
    api = BillingApiClient(settings.api_base_url, subscription_key=settings.apim_subscription_key,
                           timeout=settings.http_timeout_seconds)
    docs = DocsClient(settings.mcp_url)
    provider = build_provider(settings)
    agent: BillingAgent | None = None

    print(f"Billing assistant ({provider.name}). API: {settings.api_base_url}  MCP: {settings.mcp_url}")
    print("Type /help for commands. Log in with /login <subscriberNo>.\n")
    try:
        while True:
            try:
                line = (await _read("you> ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line in ("/quit", "/exit"):
                break
            if line == "/help":
                print(HELP)
                continue
            if line == "/trace":
                show_trace = not show_trace
                print(f"Tool trace {'on' if show_trace else 'off'}.")
                continue
            if line == "/logout":
                api.logout()
                agent = None
                print("Logged out.")
                continue
            if line.startswith("/login"):
                parts = line.split()
                if len(parts) != 2:
                    print("Usage: /login <subscriberNo>")
                    continue
                password = await asyncio.to_thread(getpass.getpass, "password: ")
                try:
                    await api.login(parts[1], password)
                except ApiError as exc:
                    print(f"Login failed: {exc.message}")
                    continue
                except ApiUnavailable:
                    print(f"Billing API not reachable at {settings.api_base_url} (cloud services may be waking up after idle; try again in ~30 s)")
                    continue
                agent = BillingAgent(provider, ToolExecutor(api, docs, parts[1]))
                print(f"Logged in as {parts[1]}.")
                continue
            if agent is None:
                print("Please log in first: /login <subscriberNo>")
                continue

            reply = await agent.handle(line)
            if show_trace:
                for t in reply.trace:
                    args = ", ".join(f"{k}={v}" for k, v in t.arguments.items())
                    print(f"  [{trace_label(t.tool)}] {t.tool}({args}) -> {'ok' if t.ok else 'failed'}: {t.summary}")
            print(f"assistant> {reply.text}\n")
    finally:
        await api.aclose()
        usage = getattr(provider, "usage", None)
        if usage is not None and usage.calls:
            print(f"LLM usage this session: {usage.calls} calls, {usage.prompt_tokens} input tokens, "
                  f"{usage.output_tokens} output tokens, {usage.thinking_tokens} thinking tokens.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Billing assistant CLI")
    parser.add_argument("--trace", action="store_true", help="show tool calls")
    asyncio.run(main_async(parser.parse_args().trace))


if __name__ == "__main__":
    main()
