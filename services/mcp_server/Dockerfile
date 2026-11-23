# MCP documentation server image. Build context: services/mcp_server
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY billing_docs ./billing_docs
COPY data ./data
RUN useradd --system --uid 10001 --no-create-home appuser
USER appuser

# Streamable HTTP on 0.0.0.0:8000/mcp. Set MCP_ALLOWED_HOSTS to the public host name in the cloud.
ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8000
EXPOSE 8000

CMD ["python", "-m", "billing_docs.server"]
