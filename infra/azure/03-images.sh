#!/usr/bin/env bash
# Step 3: Azure Container Registry (Basic, ~$5/month) and the two service images.
# Azure for Students blocks ACR Tasks (`az acr build` -> TasksOperationsNotAllowed), so images are
# built locally with Docker for linux/amd64 and pushed. Set USE_ACR_TASKS=1 to build in Azure instead.
source "$(dirname "$0")/config.sh"
REGISTRY="$ACR_NAME.azurecr.io"

if ! az acr show -n "$ACR_NAME" --output none 2>/dev/null; then
  log "Creating container registry $ACR_NAME (Basic)"
  az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --location "$LOCATION" --output none
fi

if [ "${USE_ACR_TASKS:-0}" != "1" ]; then
  log "Logging Docker in to $REGISTRY"
  az acr login --name "$ACR_NAME" --output none
fi

for svc in billing_api:billing-api mcp_server:billing-mcp; do
  dir="${svc%%:*}"; image="${svc##*:}"
  if [ "${USE_ACR_TASKS:-0}" = "1" ]; then
    log "Building $image:$IMAGE_TAG in Azure (ACR Tasks)"
    az acr build --registry "$ACR_NAME" --image "$image:$IMAGE_TAG" --platform linux/amd64 \
      "$REPO_ROOT/services/$dir" --output none
  else
    log "Building $image:$IMAGE_TAG locally for linux/amd64 and pushing"
    docker buildx build --platform linux/amd64 --provenance=false \
      -t "$REGISTRY/$image:$IMAGE_TAG" --push "$REPO_ROOT/services/$dir"
  fi
done
save_state BUILT_IMAGE_TAG "$IMAGE_TAG"

for image in billing-api billing-mcp; do
  echo "  $image tags: $(az acr repository show-tags -n "$ACR_NAME" --repository "$image" -o tsv | tr '\n' ' ')"
done
