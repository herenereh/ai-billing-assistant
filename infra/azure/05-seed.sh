#!/usr/bin/env bash
# Step 5: load the demo data (idempotent) inside the running Billing API container.
# Runs inside Azure, so the database never has to be opened to your IP address.
# Express Container Apps environments support neither Jobs nor managed identities, so the seed
# runs through `az containerapp exec` (the exec command takes no shell quoting, hence `env PYTHONPATH`).
source "$(dirname "$0")/config.sh"
: "${API_FQDN:?run 04-container-apps.sh first}" "${GATEWAY_SECRET:?run 04-container-apps.sh first}"

log "Waking the Billing API (it scales to zero when idle)"
for _ in $(seq 1 30); do curl -fsS "https://$API_FQDN/health" >/dev/null 2>&1 && break; sleep 5; done

log "Running the seed inside $CA_API"
# `script` gives az a pseudo-terminal, which `containerapp exec` requires.
script -q /dev/null az containerapp exec -g "$RESOURCE_GROUP" -n "$CA_API" \
  --command "env PYTHONPATH=/app python -m app.seed" 2>&1 | grep -E "total|Seed|already|Error" || true

log "Check (backend called with the gateway header, as API Management will)"
curl -sS -H "X-Gateway-Secret: $GATEWAY_SECRET" \
  "https://$API_FQDN/api/v1/bills?subscriberNo=5551001&month=10&year=2026"; echo
