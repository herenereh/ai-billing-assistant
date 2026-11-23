"""Gemini adapter tests with a scripted fake client: no network, no API key, no cost."""
# pyright: reportOptionalIterable=false, reportOptionalMemberAccess=false, reportCallIssue=false

from types import SimpleNamespace

import pytest
from google.genai import errors, types

from billing_agent.agent import BillingAgent
from billing_agent.cli import build_provider
from billing_agent.config import AgentSettings
from billing_agent.llm.gemini import GeminiProvider
from billing_agent.tools import TOOL_SPECS, ToolExecutor
from tests.conftest import TODAY

pytestmark = pytest.mark.anyio

SIGNATURE = b"opaque-thought-signature"


def model_turn(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=20, thoughts_token_count=5),
    )


def call(name: str, args: dict, call_id: str | None = None, signature: bytes | None = None) -> types.Part:
    return types.Part(function_call=types.FunctionCall(id=call_id, name=name, args=args), thought_signature=signature)


def text(t: str) -> types.Part:
    return types.Part(text=t)


class FakeGeminiClient:
    """Mimics client.aio.models.generate_content and records every request."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.requests: list[dict] = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, *, model, contents, config):
        self.requests.append({"model": model, "contents": contents, "config": config})
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
async def make_agent(api, fake_docs):
    await api.login("5551001", "pw1")

    def _make(*responses):
        fake = FakeGeminiClient(*responses)
        provider = GeminiProvider("", "gemini-test-model", client=fake)
        agent = BillingAgent(provider, ToolExecutor(api, fake_docs, "5551001"), today=lambda: TODAY)
        return agent, fake, provider

    return _make


# --- conversion ----------------------------------------------------------------

def test_tools_use_raw_json_schema():
    [tool] = GeminiProvider.to_tools(TOOL_SPECS)
    decls = {d.name: d for d in tool.function_declarations}
    assert set(decls) == {"search_billing_documentation", "query_bill", "query_bill_detailed", "pay_bill"}
    assert decls["pay_bill"].parameters_json_schema == next(t.parameters for t in TOOL_SPECS if t.name == "pay_bill")


def test_tool_results_are_grouped_and_raw_model_turn_replayed():
    raw = types.Content(role="model", parts=[call("query_bill", {"month": 10, "year": 2026}, "c1", SIGNATURE),
                                            call("search_billing_documentation", {"query": "x"}, "c2")])
    contents = GeminiProvider.to_contents([
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": None, "tool_calls": [], "provider_raw": raw},
        {"role": "tool", "name": "query_bill", "provider_call_id": "c1", "content": {"ok": True}},
        {"role": "tool", "name": "search_billing_documentation", "provider_call_id": "c2", "content": {"ok": True}},
        {"role": "assistant", "content": "Please confirm..."},
    ])
    assert [c.role for c in contents] == ["user", "model", "user", "model"]
    assert contents[1] is raw                                      # signatures kept byte-for-byte
    responses = [p.function_response for p in contents[2].parts]
    assert [(r.id, r.name) for r in responses] == [("c1", "query_bill"), ("c2", "search_billing_documentation")]


# --- agent loop with Gemini ---------------------------------------------------------

async def test_api_only_question(make_agent):
    agent, fake, provider = make_agent(
        model_turn(call("query_bill", {"month": 10, "year": 2026}, "c1", SIGNATURE)),
        model_turn(text("Your October 2026 bill is $80.00 and unpaid.")),
    )
    reply = await agent.handle("What is my October bill?")
    assert [t.tool for t in reply.trace] == ["query_bill"]
    assert reply.text == "Your October 2026 bill is $80.00 and unpaid."

    first, second = fake.requests
    assert first["model"] == "gemini-test-model"
    assert first["config"].automatic_function_calling.disable is True
    assert "logged-in subscriber is 5551001" in first["config"].system_instruction
    replayed_call = second["contents"][1].parts[0]
    assert replayed_call.thought_signature == SIGNATURE
    result = second["contents"][2].parts[0].function_response
    assert result.id == "c1" and result.response["total"] == 80.0
    assert (provider.usage.calls, provider.usage.prompt_tokens, provider.usage.output_tokens) == (2, 200, 40)


async def test_combined_question_runs_parallel_calls(make_agent, fake_docs):
    agent, fake, _ = make_agent(
        model_turn(call("query_bill_detailed", {"month": 10, "year": 2026}, "c1"),
                   call("search_billing_documentation", {"query": "extra internet pricing"}, "c2")),
        model_turn(text("You used 35 GB; above 20 GB each 10 GB block costs $10 (§3.2).")),
    )
    reply = await agent.handle("Why is my October bill higher?")
    assert [t.tool for t in reply.trace] == ["query_bill_detailed", "search_billing_documentation"]
    assert fake_docs.queries == ["extra internet pricing"]
    assert len(fake.requests[1]["contents"][2].parts) == 2        # both results in one turn


async def test_gemini_cannot_pay_without_user_confirmation(make_agent, fake_api):
    agent, fake, _ = make_agent(
        model_turn(call("pay_bill", {"month": 10, "year": 2026}, "c1")),
    )
    reply = await agent.handle("Pay my bill")
    assert reply.awaiting_confirmation
    assert "Amount:     $80.00" in reply.text                       # prompt written by the agent, not the LLM
    assert fake_api.payment_requests() == []
    assert len(fake.requests) == 1                                  # LLM not asked to phrase the confirmation

    done = await agent.handle("yes")
    assert len(fake_api.payment_requests()) == 1
    assert done.text.startswith("Payment successful")


async def test_two_payments_in_one_turn_are_not_both_prepared(make_agent, fake_api):
    agent, _, _ = make_agent(
        model_turn(call("pay_bill", {"month": 10, "year": 2026, "amount": 10}, "c1"),
                   call("pay_bill", {"month": 10, "year": 2026, "amount": 20}, "c2")),
    )
    reply = await agent.handle("pay 10 and then 20")
    assert [t.ok for t in reply.trace] == [True, False]
    assert "Amount:     $10.00" in reply.text
    tool_msgs = [m for m in agent.messages if m["role"] == "tool"]
    assert len(tool_msgs) == 2                                      # every call got a result


async def test_gemini_api_error_is_reported_and_history_stays_valid(make_agent):
    agent, _, _ = make_agent(
        errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}),
        model_turn(text("Extra internet costs $10 per 10 GB block (§3.2).")),
    )
    failed = await agent.handle("How much does extra internet cost?")
    assert "unavailable right now" in failed.text
    assert agent.messages == []
    ok = await agent.handle("How much does extra internet cost?")
    assert "§3.2" in ok.text


async def test_blocked_response_gets_a_safe_answer(make_agent):
    agent, _, _ = make_agent(types.GenerateContentResponse(candidates=[]))
    reply = await agent.handle("something")
    assert reply.text.startswith("Sorry, I can't answer that")


async def test_injected_subscriber_number_is_ignored(make_agent, fake_api):
    agent, _, _ = make_agent(
        model_turn(call("query_bill", {"month": 10, "year": 2026, "subscriberNo": "5551002"}, "c1")),
        model_turn(text("done")),
    )
    await agent.handle("show 5551002's bill")
    assert not any("5551002" in str(r.url) for r in fake_api.requests)


# --- configuration -----------------------------------------------------------------

def test_gemini_requires_api_key():
    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        build_provider(AgentSettings(llm_provider="gemini", gemini_api_key=None, _env_file=None))


def test_gemini_provider_built_from_settings():
    provider = build_provider(AgentSettings(llm_provider="gemini", gemini_api_key="test-key",
                                            gemini_model="gemini-3.5-flash-lite", _env_file=None))
    assert provider.name == "gemini (gemini-3.5-flash-lite)"


def test_unknown_provider():
    with pytest.raises(SystemExit, match="Unknown LLM_PROVIDER"):
        build_provider(AgentSettings(llm_provider="gpt", _env_file=None))


async def test_free_tier_rate_limit_message(make_agent):
    agent, _, _ = make_agent(
        errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}),
    )
    reply = await agent.handle("How much does extra internet cost?")
    assert "rate limit reached (free tier)" in reply.text


async def test_last_round_offers_no_tools_so_the_model_must_answer(make_agent):
    from billing_agent.agent import MAX_TOOL_ROUNDS
    searches = [model_turn(call("search_billing_documentation", {"query": f"q{i}"}, f"c{i}"))
                for i in range(MAX_TOOL_ROUNDS - 1)]
    agent, fake, _ = make_agent(*searches, model_turn(text("Final answer from what was found.")))
    reply = await agent.handle("Why is my bill higher?")
    assert reply.text == "Final answer from what was found."
    assert fake.requests[-1]["config"].tools is None
    assert all(r["config"].tools for r in fake.requests[:-1])
