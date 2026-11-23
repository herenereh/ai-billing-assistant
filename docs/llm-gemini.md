# LLM: Gemini setup and cost

The agent works with two interchangeable "brains" (`LLM_PROVIDER` in `services/agent/.env`):

| Provider | What it is | Cost | Used by |
|---|---|---|---|
| `rule-based` (default) | Keyword routing + templated answers, no LLM | $0 | Unit tests, offline demo |
| `gemini` | Google Gemini via the official `google-genai` SDK | Free tier or pay-per-token | Real conversations |

Both plug into the same agent loop (`billing_agent/agent.py`). The LLM only **chooses tools and writes
the answer**; the agent executes every tool call. Payment confirmation, identity (subscriber number
taken only from the login) and duplicate-payment protection are enforced in code, so the LLM cannot
bypass them.

## Setup

1. Create an API key at <https://aistudio.google.com/apikey> (Google account needed).
2. Copy the example settings and add the key (the file is git-ignored; never commit it):
   ```bash
   cd services/agent && cp .env.example .env
   ```
   Then edit `.env`:
   ```
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=<your key>
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```
3. Start the Billing API and MCP server, then the chat:
   ```bash
   uv run python -m billing_agent.cli --trace
   ```
   On exit the CLI prints the session's token usage.

## Model choice

Default: **`gemini-3.5-flash-lite`**, a stable model that Google's model page recommends for new projects,
with a free tier. Any other Gemini model can be set with `GEMINI_MODEL`.

## Pricing (Google AI Studio pricing page, checked 2026-11-23, Standard tier, per 1M tokens)

| Model | Free tier | Paid input | Paid output | Free-tier data used to improve Google products |
|---|---|---|---|---|
| `gemini-3.5-flash-lite` | Yes | $0.30 | $2.50 | Yes (paid tier: No) |

Free-tier rate limits are set per Google Cloud project and shown in AI Studio.

## Decision: free tier

This project uses the **Gemini free tier** (an AI Studio key without billing enabled), so LLM cost is **$0**.
Free-tier rate limits apply per project; when they are hit, the assistant answers
"Gemini rate limit reached (free tier); wait a minute and try again" instead of failing.

Free-tier limits shown in AI Studio for this project (2026-11-23), and what they allow:

| Limit | `gemini-3.5-flash-lite` free tier | ≈ Questions (2 calls each) |
|---|---|---|
| Requests per minute | 15 | ~7 per minute |
| Tokens per minute | 250K | not a constraint |
| Requests per day | 500 | ~250 per day |

Measured in the first live test: 3 calls used 5.91K tokens, about 2K tokens per call.

## Low-cost / testable approach

- All unit tests use the rule-based provider or a scripted fake Gemini client: no key, no network, $0.
- Interactive demos can run on the Gemini free tier. All billing data in this project is fictitious,
  so the free tier's data-use terms are acceptable here.
- Thinking tokens are billed as output; `max_output_tokens` is capped at 2048 per call.

## If the paid tier were used (estimate per question)

A typical question takes 2 model calls (choose tools, then answer). Each call sends the system prompt,
the 4 tool definitions and the conversation so far.

| | Tokens (estimate) | Cost |
|---|---|---|
| Input (2 calls) | ~4,000 | 4,000 × $0.30 / 1M ≈ $0.0012 |
| Output incl. thinking (2 calls) | ~400 | 400 × $2.50 / 1M ≈ $0.0010 |
| **Per question** | | **≈ $0.002** |

So 100 demo questions cost about $0.20 on the paid tier, or $0 on the free tier.
These are estimates; replace them with the measured numbers that the CLI and
`billing_agent.demo` print after a real run.
