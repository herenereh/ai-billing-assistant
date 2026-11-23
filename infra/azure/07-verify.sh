#!/usr/bin/env bash
# Step 7: end-to-end checks through the gateway; writes docs/logs/gateway_checks.md for the README.
# Uses the seed test account 5551001 (password from services/billing_api/app/seed.py).
source "$(dirname "$0")/config.sh"
: "${GATEWAY_URL:?run 06-api-gateway.sh first}" "${APIM_SUBSCRIPTION_KEY:?}"

GW="$GATEWAY_URL/api/v1"
KEY="Ocp-Apim-Subscription-Key: $APIM_SUBSCRIPTION_KEY"
OUT="$REPO_ROOT/docs/logs/gateway_checks.md"
DEMO_PASSWORD="${DEMO_PASSWORD:-Demo#1001}"

check() {  # check "title" expected_status curl-args...
  local title="$1" expected="$2"; shift 2
  local body status
  body="$(curl -sS -w '\n%{http_code}' "$@")"
  status="$(tail -n1 <<<"$body")"; body="$(sed '$d' <<<"$body")"
  local mark="✅"; [ "$status" = "$expected" ] || mark="❌"
  printf '### %s %s\n\n`HTTP %s` (expected %s)\n\n```json\n%s\n```\n\n' "$mark" "$title" "$status" "$expected" "$body" >> "$OUT"
  echo "$mark $title -> $status"
}

printf '# API Gateway checks\n\n- Gateway: `%s`\n\n' "$GW" > "$OUT"

TOKEN="$(curl -sS -H "$KEY" -H 'Content-Type: application/json' \
  -d "{\"subscriberNo\":\"5551001\",\"password\":\"$DEMO_PASSWORD\"}" "$GW/auth/login" | python3 -c 'import sys,json; print(json.load(sys.stdin)["accessToken"])')"

check "Public route: GET /bills (Query Bill)" 200 -H "$KEY" "$GW/bills?subscriberNo=5551001&month=10&year=2026"
check "Protected route without token: GET /bills/detailed" 401 -H "$KEY" "$GW/bills/detailed?month=10&year=2026"
check "Protected route with token: GET /bills/detailed" 200 -H "$KEY" -H "Authorization: Bearer $TOKEN" "$GW/bills/detailed?month=10&year=2026&pageSize=2"
check "Forged token rejected at gateway" 401 -H "$KEY" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI1NTUxMDAyIn0.x" "$GW/bills/detailed?month=10&year=2026"
check "Another subscriber's bill with own token" 403 -H "$KEY" -H "Authorization: Bearer $TOKEN" "$GW/bills/detailed?month=10&year=2026&subscriberNo=5551002"
check "Business error passed through: unknown period" 404 -H "$KEY" "$GW/bills?subscriberNo=5551001&month=4&year=2025"
check "Missing APIM subscription key" 401 "$GW/bills?subscriberNo=5551001&month=10&year=2026"
check "Bypassing the gateway (direct backend call)" 403 "https://$API_FQDN/api/v1/bills?subscriberNo=5551001&month=10&year=2026"

echo "Saved $OUT"
