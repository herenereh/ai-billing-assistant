# Billing REST API image (FastAPI + Alembic). Build context: services/billing_api
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Dependencies first (cached layer), exactly as pinned in uv.lock, without dev/test tools.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh \
    && useradd --system --uid 10001 --no-create-home appuser
USER appuser

ENV APP_ENV=production \
    PORT=8000
EXPOSE 8000

# Applies database migrations, then starts the API. Override CMD to run e.g. `python -m app.seed`.
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["serve"]
