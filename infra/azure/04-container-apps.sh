#!/usr/bin/env bash
# Step 4: Container Apps environment + Billing API and MCP server apps (scale to zero).
source "$(dirname "$0")/config.sh"
: "${DATABASE_URL:?run 02-postgres.sh first}" "${BUILT_IMAGE_TAG:?run 03-images.sh first}"
IMAGE_TAG="$BUILT_IMAGE_TAG"   # the tag that was actually pushed

if [ -z "${JWT_SECRET:-}" ]; then save_state JWT_SECRET "$(random_secret 48)"; fi
if [ -z "${GATEWAY_SECRET:-}" ]; then save_state GATEWAY_SECRET "$(random_secret 40)"; fi
REGISTRY="$ACR_NAME.azurecr.io"
# Express Container Apps environments do not support managed identity for registry pulls,
# so the registry admin credentials are used (stored by Container Apps as a secret).
az acr update -n "$ACR_NAME" --admin-enabled true --output none
ACR_USER="$(az acr credential show -n "$ACR_NAME" --query username -o tsv)"
ACR_PASSWORD="$(az acr credential show -n "$ACR_NAME" --query "passwords[0].value" -o tsv)"

if ! az containerapp env show -g "$RESOURCE_GROUP" -n "$CA_ENV" --output none 2>/dev/null; then
  log "Creating Container Apps environment $CA_ENV (no Log Analytics workspace, to avoid cost)"
  az containerapp env create -g "$RESOURCE_GROUP" -n "$CA_ENV" --location "$LOCATION" \
    --logs-destination none --output none
fi

API_SECRETS=(db-url="$DATABASE_URL" jwt-secret="$JWT_SECRET" gateway-secret="$GATEWAY_SECRET")
API_ENV=(APP_ENV=production DATABASE_URL=secretref:db-url JWT_SECRET=secretref:jwt-secret GATEWAY_SECRET=secretref:gateway-secret)

if az containerapp show -g "$RESOURCE_GROUP" -n "$CA_API" --output none 2>/dev/null; then
  log "Updating $CA_API to $IMAGE_TAG"
  az containerapp registry set -g "$RESOURCE_GROUP" -n "$CA_API" --server "$REGISTRY" \
    --username "$ACR_USER" --password "$ACR_PASSWORD" --output none
  az containerapp secret set -g "$RESOURCE_GROUP" -n "$CA_API" --secrets "${API_SECRETS[@]}" --output none
  az containerapp update -g "$RESOURCE_GROUP" -n "$CA_API" --image "$REGISTRY/billing-api:$IMAGE_TAG" \
    --set-env-vars "${API_ENV[@]}" --output none
else
  log "Creating Billing API app $CA_API (migrations run on start)"
  az containerapp create -g "$RESOURCE_GROUP" -n "$CA_API" --environment "$CA_ENV" \
    --image "$REGISTRY/billing-api:$IMAGE_TAG" \
    --registry-server "$REGISTRY" --registry-username "$ACR_USER" --registry-password "$ACR_PASSWORD" \
    --target-port 8000 --ingress external \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
    --secrets "${API_SECRETS[@]}" --env-vars "${API_ENV[@]}" --output none
fi
save_state API_FQDN "$(az containerapp show -g "$RESOURCE_GROUP" -n "$CA_API" --query properties.configuration.ingress.fqdn -o tsv)"

if az containerapp show -g "$RESOURCE_GROUP" -n "$CA_MCP" --output none 2>/dev/null; then
  log "Updating $CA_MCP to $IMAGE_TAG"
  az containerapp registry set -g "$RESOURCE_GROUP" -n "$CA_MCP" --server "$REGISTRY" \
    --username "$ACR_USER" --password "$ACR_PASSWORD" --output none
  az containerapp update -g "$RESOURCE_GROUP" -n "$CA_MCP" --image "$REGISTRY/billing-mcp:$IMAGE_TAG" --output none
else
  log "Creating MCP server app $CA_MCP"
  az containerapp create -g "$RESOURCE_GROUP" -n "$CA_MCP" --environment "$CA_ENV" \
    --image "$REGISTRY/billing-mcp:$IMAGE_TAG" \
    --registry-server "$REGISTRY" --registry-username "$ACR_USER" --registry-password "$ACR_PASSWORD" \
    --target-port 8000 --ingress external \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi --output none
fi
save_state MCP_FQDN "$(az containerapp show -g "$RESOURCE_GROUP" -n "$CA_MCP" --query properties.configuration.ingress.fqdn -o tsv)"
# DNS-rebinding protection: accept only our public host name.
az containerapp update -g "$RESOURCE_GROUP" -n "$CA_MCP" --set-env-vars "MCP_ALLOWED_HOSTS=$MCP_FQDN" --output none

log "Waiting for health checks"
for url in "https://$API_FQDN/health" "https://$MCP_FQDN/health"; do
  for _ in $(seq 1 30); do curl -fsS "$url" >/dev/null 2>&1 && break; sleep 5; done
  echo "  $url -> $(curl -sS "$url")"
done
echo "  Direct API call without gateway (expect 403 GATEWAY_REQUIRED):"
curl -sS "https://$API_FQDN/api/v1/bills?subscriberNo=5551001&month=10&year=2026"; echo
