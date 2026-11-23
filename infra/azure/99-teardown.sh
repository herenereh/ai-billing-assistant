#!/usr/bin/env bash
# Delete EVERYTHING in the resource group (database data included). Cannot be undone.
source "$(dirname "$0")/config.sh"

read -r -p "Delete resource group '$RESOURCE_GROUP' and all its resources permanently? Type the name to confirm: " answer
[ "$answer" = "$RESOURCE_GROUP" ] || { echo "Cancelled."; exit 1; }
az group delete --name "$RESOURCE_GROUP" --yes --no-wait
echo "Deletion started. State file kept at $STATE_FILE (delete it to start fresh)."
