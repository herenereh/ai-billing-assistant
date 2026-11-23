"""Provider-neutral LLM interface. Claude or Gemini adapters (later) implement LLMProvider.

Conversation messages are plain dicts:
    {"role": "user", "content": "..."}
    {"role": "assistant", "content": "..." | None, "tool_calls": [ToolCall, ...]}
    {"role": "tool", "tool_call_id": "...", "name": "...", "content": {...}}
An adapter translates these and the ToolSpec JSON Schemas into its own SDK's format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from billing_agent.tools import ToolSpec


class LLMUnavailable(Exception):
    """The LLM provider could not be reached or returned an error."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    provider_id: str | None = None   # the provider's own call ID, echoed back with the result


@dataclass(frozen=True)
class LLMResponse:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider_raw: Any = None         # provider-native message to replay unchanged (e.g. Gemini thought signatures)


@dataclass(frozen=True)
class AgentContext:
    subscriber_no: str
    today: date


class LLMProvider(Protocol):
    name: str

    async def complete(
        self, system: str, messages: list[dict], tools: list[ToolSpec], context: AgentContext
    ) -> LLMResponse:
        """Return either tool calls to run, or the final answer text."""
        ...
