"""Gemini adapter (Google Gen AI SDK, `google-genai`).

The agent loop stays the same: Gemini only decides which tools to call and writes the answer.
Automatic function calling is disabled so the agent, not the SDK, executes every tool call
(and keeps the payment confirmation and identity rules).

Gemini 3+ models attach "thought signatures" to function-call parts that must be sent back
unchanged. We keep the model's original Content on the assistant message (`provider_raw`) and
replay it as-is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from google import genai
from google.genai import errors, types

from billing_agent.llm.base import AgentContext, LLMResponse, LLMUnavailable, ToolCall
from billing_agent.tools import ToolSpec

DEFAULT_MODEL = "gemini-3.5-flash-lite"


@dataclass
class TokenUsage:
    calls: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    per_call: list[dict] = field(default_factory=list)


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, *, client: Any = None, max_output_tokens: int = 2048):
        if not api_key and client is None:
            raise ValueError("GEMINI_API_KEY is not set")
        self.model = model
        self.name = f"gemini ({model})"
        self._client = client or genai.Client(api_key=api_key)
        self._max_output_tokens = max_output_tokens
        self.usage = TokenUsage()

    # --- conversion ---------------------------------------------------------------

    @staticmethod
    def to_tools(tools: list[ToolSpec]) -> list[types.Tool]:
        return [types.Tool(function_declarations=[
            types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters)
            for t in tools
        ])]

    @staticmethod
    def to_contents(messages: list[dict]) -> list[types.Content]:
        contents: list[types.Content] = []
        pending_results: list[types.Part] = []

        def flush_results() -> None:
            if pending_results:
                contents.append(types.Content(role="user", parts=list(pending_results)))
                pending_results.clear()

        for m in messages:
            role = m["role"]
            if role == "tool":
                pending_results.append(types.Part(function_response=types.FunctionResponse(
                    id=m.get("provider_call_id"), name=m["name"], response=m["content"],
                )))
                continue
            flush_results()
            if role == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=m["content"])]))
            elif role == "assistant":
                raw = m.get("provider_raw")
                if isinstance(raw, types.Content):
                    contents.append(raw)  # replay unchanged, keeps thought signatures
                    continue
                parts = [types.Part(text=m["content"])] if m.get("content") else []
                parts += [types.Part(function_call=types.FunctionCall(name=c.name, args=c.arguments))
                          for c in m.get("tool_calls", [])]
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
        flush_results()
        return contents

    # --- call ---------------------------------------------------------------------

    async def complete(
        self, system: str, messages: list[dict], tools: list[ToolSpec], context: AgentContext
    ) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=cast(types.ToolListUnion, self.to_tools(tools)) if tools else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            max_output_tokens=self._max_output_tokens,
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model, contents=self.to_contents(messages), config=config
            )
        except errors.APIError as exc:
            if getattr(exc, "code", None) == 429:
                raise LLMUnavailable("Gemini rate limit reached (free tier); wait a minute and try again") from exc
            raise LLMUnavailable(f"Gemini API error {getattr(exc, 'code', '')}: {getattr(exc, 'message', exc)}") from exc
        except Exception as exc:  # network errors
            raise LLMUnavailable(f"Gemini request failed: {exc}") from exc

        self._record_usage(response)
        if not response.candidates or response.candidates[0].content is None:
            reason = getattr(response.prompt_feedback, "block_reason", None) if response.prompt_feedback else None
            return LLMResponse(text=f"Sorry, I can't answer that{f' ({reason})' if reason else ''}.")

        content = response.candidates[0].content
        calls = [
            ToolCall(id=fc.id or f"gemini_{i}", name=fc.name or "", arguments=dict(fc.args or {}),
                     provider_id=fc.id)
            for i, p in enumerate(content.parts or [])
            if (fc := p.function_call) is not None
        ]
        text = "".join(p.text for p in content.parts or [] if p.text and not p.thought) or None
        return LLMResponse(text=text, tool_calls=calls, provider_raw=content)

    def _record_usage(self, response: Any) -> None:
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return
        entry = {
            "prompt": meta.prompt_token_count or 0,
            "output": meta.candidates_token_count or 0,
            "thinking": meta.thoughts_token_count or 0,
        }
        self.usage.calls += 1
        self.usage.prompt_tokens += entry["prompt"]
        self.usage.output_tokens += entry["output"]
        self.usage.thinking_tokens += entry["thinking"]
        self.usage.per_call.append(entry)
