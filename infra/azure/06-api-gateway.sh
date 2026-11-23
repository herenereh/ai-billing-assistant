#!/usr/bin/env bash
# Step 6: Azure API Management (Consumption tier) in front of the Billing API.
#   Public URL:  https://<apim>.azure-api.net/api/v1/...   (versioned: Segment scheme, "v1")
#   Gateway checks: APIM subscription key (+ rate limit 60 calls/min per key),
#                   JWT validation on protected operations, then forwards with X-Gateway-Secret.
# Consumption notes: rate-limit-by-key is not available, rate-limit counts per subscription key.
source "$(dirname "$0")/config.sh"
: "${API_FQDN:?run 04-container-apps.sh first}" "${JWT_SECRET:?}" "${GATEWAY_SECRET:?}"

SUB_ID="$(az account show --query id -o tsv)"
APIM_ID="/subscriptions/$SUB_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.ApiManagement/service/$APIM_NAME"
ARM_VERSION="2022-08-01"
API_ID="billing-api-v1"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

if ! az apim show -g "$RESOURCE_GROUP" -n "$APIM_NAME" --output none 2>/dev/null; then
  log "Creating API Management $APIM_NAME (Consumption, $APIM_LOCATION) - can take several minutes"
  az apim create -g "$RESOURCE_GROUP" -n "$APIM_NAME" --location "$APIM_LOCATION" --sku-name Consumption \
    --publisher-email "$APIM_PUBLISHER_EMAIL" --publisher-name "$APIM_PUBLISHER_NAME" --output none
fi
GATEWAY_URL="$(az apim show -g "$RESOURCE_GROUP" -n "$APIM_NAME" --query gatewayUrl -o tsv)"
save_state GATEWAY_URL "$GATEWAY_URL"

log "Named values (secrets stored in APIM, referenced as {{name}} in policies)"
JWT_KEY_B64="$(printf '%s' "$JWT_SECRET" | base64 | tr -d '\n')"   # validate-jwt wants the key base64-encoded
az apim nv create -g "$RESOURCE_GROUP" --service-name "$APIM_NAME" --named-value-id jwt-signing-key \
  --display-name jwt-signing-key --value "$JWT_KEY_B64" --secret true --output none
az apim nv create -g "$RESOURCE_GROUP" --service-name "$APIM_NAME" --named-value-id gateway-secret \
  --display-name gateway-secret --value "$GATEWAY_SECRET" --secret true --output none

log "Version set + import of the Billing API OpenAPI document as v1"
az apim api versionset create -g "$RESOURCE_GROUP" --service-name "$APIM_NAME" --version-set-id billing-api \
  --display-name "Billing API" --versioning-scheme Segment --output none
# The backend's routes already start with /api/v1; APIM adds that prefix itself (path "api" + version "v1"),
# so strip it from the imported operations and leave out /health.
curl -fsS "https://$API_FQDN/openapi.json" -o "$TMP/openapi.json"
python3 - "$TMP/openapi.json" "$TMP/openapi.v1.json" <<'PY'
import json, sys

# FastAPI emits OpenAPI 3.1; the APIM importer expects 3.0 keywords. Convert the few that differ.
def to_30(node):
    if isinstance(node, list):
        return [to_30(n) for n in node]
    if not isinstance(node, dict):
        return node
    node = {k: to_30(v) for k, v in node.items()}
    for bound, plain in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
        if isinstance(node.get(bound), (int, float)) and not isinstance(node.get(bound), bool):
            node[plain], node[bound] = node[bound], True
    if isinstance(node.get("examples"), list):                          # schema-level examples (3.1)
        node["example"] = node.pop("examples")[0] if node["examples"] else None
    any_of = node.get("anyOf")
    if isinstance(any_of, list) and {"type": "null"} in any_of:          # Optional[X] -> nullable X
        rest = [s for s in any_of if s != {"type": "null"}]
        node.pop("anyOf")
        node["nullable"] = True
        if len(rest) == 1:
            node.update(rest[0])
        else:
            node["anyOf"] = rest
    if node.get("type") == "null":
        node.pop("type")
        node["nullable"] = True
    return node

doc = json.load(open(sys.argv[1]))
doc["paths"] = {p.removeprefix("/api/v1") or "/": v for p, v in doc["paths"].items() if p.startswith("/api/v1/")}
doc.pop("servers", None)
doc = to_30(doc)
doc["openapi"] = "3.0.3"
json.dump(doc, open(sys.argv[2], "w"))
PY
az apim api import -g "$RESOURCE_GROUP" --service-name "$APIM_NAME" --api-id "$API_ID" \
  --path api --api-version v1 --api-version-set-id billing-api \
  --display-name "Billing API" --service-url "https://$API_FQDN/api/v1" --protocols https \
  --specification-format OpenApiJson --specification-path "$TMP/openapi.v1.json" \
  --subscription-required true --output none

log "API policy: rate limit, JWT validation on protected operations, gateway header"
cat > "$TMP/policy.xml" <<'XML'
<policies>
  <inbound>
    <base />
    <rate-limit calls="60" renewal-period="60" />
    <choose>
      <!-- Public per the app spec: POST /auth/login and GET /bills (Query Bill). Everything else needs a JWT.
           APIM keeps required query parameters in UrlTemplate ("/bills?subscriberNo=..."), so compare the path part. -->
      <when condition="@(!context.Operation.UrlTemplate.StartsWith("/auth/") &amp;&amp; !(context.Request.Method == "GET" &amp;&amp; context.Operation.UrlTemplate.Split('?')[0] == "/bills"))">
        <validate-jwt header-name="Authorization" require-scheme="Bearer" failed-validation-httpcode="401"
                      failed-validation-error-message="Missing or invalid bearer token">
          <issuer-signing-keys><key>{{jwt-signing-key}}</key></issuer-signing-keys>
          <audiences><audience>billing-clients</audience></audiences>
          <issuers><issuer>billing-api</issuer></issuers>
        </validate-jwt>
      </when>
    </choose>
    <set-header name="X-Gateway-Secret" exists-action="override"><value>{{gateway-secret}}</value></set-header>
  </inbound>
  <backend><base /></backend>
  <outbound>
    <base />
    <set-header name="X-Gateway-Secret" exists-action="delete" />
  </outbound>
  <on-error>
    <base />
    <choose>
      <when condition="@(context.LastError.Source == "validate-jwt")">
        <return-response>
          <set-status code="401" reason="Unauthorized" />
          <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
          <set-body>{"error":{"code":"UNAUTHORIZED","message":"Missing or invalid bearer token (rejected by the API Gateway)"}}</set-body>
        </return-response>
      </when>
    </choose>
  </on-error>
</policies>
XML
python3 -c 'import json,sys; print(json.dumps({"properties": {"format": "rawxml", "value": open(sys.argv[1]).read()}}))' \
  "$TMP/policy.xml" > "$TMP/policy.json"
az rest --method put --url "https://management.azure.com$APIM_ID/apis/$API_ID/policies/policy?api-version=$ARM_VERSION" \
  --body @"$TMP/policy.json" --output none

log "Subscription key for the agent (scoped to this API)"
az rest --method put --url "https://management.azure.com$APIM_ID/subscriptions/agent-cli?api-version=$ARM_VERSION" \
  --body "{\"properties\": {\"scope\": \"/apis/$API_ID\", \"displayName\": \"Agent CLI\", \"state\": \"active\"}}" --output none
save_state APIM_SUBSCRIPTION_KEY "$(az rest --method post \
  --url "https://management.azure.com$APIM_ID/subscriptions/agent-cli/listSecrets?api-version=$ARM_VERSION" \
  --query primaryKey -o tsv)"

log "Gateway ready: $GATEWAY_URL/api/v1"
echo "Agent settings (services/agent/.env):"
echo "  API_BASE_URL=$GATEWAY_URL/api/v1"
echo "  APIM_SUBSCRIPTION_KEY=<in infra/azure/.env.deploy>"
echo "  MCP_URL=https://$MCP_FQDN/mcp"
