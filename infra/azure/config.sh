#!/usr/bin/env bash
# Shared settings for the deploy scripts. Sourced by every step; do not run directly.
# Generated secrets and resource names are kept in infra/azure/.env.deploy (git-ignored).
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$INFRA_DIR/../.." && pwd)"
STATE_FILE="$INFRA_DIR/.env.deploy"

# Region must be on the subscription's "Allowed resource deployment regions" policy list:
#   polandcentral, norwayeast, switzerlandnorth, uaenorth (germanywestcentral has no B1ms here).
LOCATION="${LOCATION:-polandcentral}"
# API Management Consumption is not offered in Poland Central (ApiManagementCreationDisabledForLocation).
APIM_LOCATION="${APIM_LOCATION:-switzerlandnorth}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-billing-assistant}"
APIM_PUBLISHER_EMAIL="${APIM_PUBLISHER_EMAIL:-billing-admin@example.com}"
APIM_PUBLISHER_NAME="${APIM_PUBLISHER_NAME:-Billing Assistant Demo}"

touch "$STATE_FILE"
chmod 600 "$STATE_FILE"
# shellcheck disable=SC1090
source "$STATE_FILE"

save_state() {  # save_state KEY VALUE  (persist a generated value for later steps)
  local key="$1" value="$2"
  grep -v "^${key}=" "$STATE_FILE" > "$STATE_FILE.tmp" || true
  printf '%s=%q\n' "$key" "$value" >> "$STATE_FILE.tmp"
  mv "$STATE_FILE.tmp" "$STATE_FILE"
  chmod 600 "$STATE_FILE"
  export "$key=$value"
}

random_secret() { python3 -c "import secrets,string; a=string.ascii_letters+string.digits; print(''.join(secrets.choice(a) for _ in range($1)))"; }

# Short random suffix so globally unique names (registry, database, gateway) don't collide.
if [ -z "${SUFFIX:-}" ]; then save_state SUFFIX "$(python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_lowercase+string.digits) for _ in range(5)))")"; fi

PG_SERVER="pg-billing-$SUFFIX"
PG_DATABASE="billing"
PG_ADMIN="billingadmin"
ACR_NAME="acrbilling$SUFFIX"
CA_ENV="cae-billing"
CA_API="ca-billing-api"
CA_MCP="ca-billing-mcp"
APIM_NAME="apim-billing-$SUFFIX"
if [ -z "${IMAGE_TAG_OVERRIDE:-}" ]; then
  IMAGE_TAG="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo latest)"
  # Images are built from the working tree; mark the tag when it has uncommitted changes.
  if [ -n "$(git -C "$REPO_ROOT" status --porcelain -- services 2>/dev/null)" ]; then IMAGE_TAG="$IMAGE_TAG-dirty-$(date +%m%d%H%M)"; fi
else
  IMAGE_TAG="$IMAGE_TAG_OVERRIDE"
fi

log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
