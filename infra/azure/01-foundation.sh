#!/usr/bin/env bash
# Step 1: register resource providers (free) and create the resource group.
source "$(dirname "$0")/config.sh"

log "Registering resource providers (one-time, free)"
for ns in Microsoft.App Microsoft.ContainerRegistry Microsoft.ApiManagement Microsoft.DBforPostgreSQL Microsoft.OperationalInsights; do
  az provider register --namespace "$ns" --wait --output none
  echo "  $ns: $(az provider show -n "$ns" --query registrationState -o tsv)"
done

log "Creating resource group $RESOURCE_GROUP in $LOCATION"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output table
