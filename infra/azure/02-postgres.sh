#!/usr/bin/env bash
# Step 2: Azure Database for PostgreSQL Flexible Server on the free-offer settings
# (Burstable B1ms, 32 GiB, no HA, locally redundant backups). Takes ~5-10 minutes.
source "$(dirname "$0")/config.sh"

if [ -z "${PG_PASSWORD:-}" ]; then save_state PG_PASSWORD "$(random_secret 32)"; fi

if az postgres flexible-server show -g "$RESOURCE_GROUP" -n "$PG_SERVER" --output none 2>/dev/null; then
  log "PostgreSQL server $PG_SERVER already exists"
else
  log "Creating PostgreSQL server $PG_SERVER (Burstable B1ms, 32 GiB) - this takes several minutes"
  az postgres flexible-server create \
    --resource-group "$RESOURCE_GROUP" --name "$PG_SERVER" --location "$LOCATION" \
    --tier Burstable --sku-name Standard_B1ms \
    --storage-size 32 --storage-auto-grow Disabled \
    --zonal-resiliency Disabled --geo-redundant-backup Disabled --backup-retention 7 \
    --version 16 \
    --admin-user "$PG_ADMIN" --admin-password "$PG_PASSWORD" \
    --public-access 0.0.0.0 \
    --yes --output none
fi

if ! az postgres flexible-server db show -g "$RESOURCE_GROUP" --server-name "$PG_SERVER" --name "$PG_DATABASE" --output none 2>/dev/null; then
  log "Creating database $PG_DATABASE"
  az postgres flexible-server db create -g "$RESOURCE_GROUP" --server-name "$PG_SERVER" --name "$PG_DATABASE" --output none
fi
# --public-access 0.0.0.0 = only Azure services (our Container Apps) may connect; no internet IPs.

PG_HOST="$PG_SERVER.postgres.database.azure.com"
save_state DATABASE_URL "postgresql+psycopg://$PG_ADMIN:$PG_PASSWORD@$PG_HOST:5432/$PG_DATABASE?sslmode=require"

log "PostgreSQL ready"
az postgres flexible-server show -g "$RESOURCE_GROUP" -n "$PG_SERVER" \
  --query "{name:name, state:state, sku:sku.name, tier:sku.tier, storageGb:storage.storageSizeGb, ha:highAvailability.mode, version:version}" -o table
