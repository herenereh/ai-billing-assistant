#!/bin/sh
# Container entrypoint for the Billing API image.
#   serve  (default) : apply migrations, then run the API
#   seed             : apply migrations, then load demo data (idempotent)
#   anything else    : run that command as-is
set -e

case "$1" in
  serve)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
      --proxy-headers --forwarded-allow-ips="*"
    ;;
  seed)
    alembic upgrade head
    exec python -m app.seed
    ;;
  *)
    exec "$@"
    ;;
esac
