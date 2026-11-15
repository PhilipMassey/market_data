#!/bin/bash
set -euo pipefail

# Sync market_data.db between local machine and Google Compute Engine VM
# Usage:
#   ./scripts/sync_db_vm.sh push [VM_NAME] [ZONE]
#   ./scripts/sync_db_vm.sh pull [VM_NAME] [ZONE]

ACTION="${1:-}"
VM_NAME="${2:-${GCE_VM_NAME:-market-data-vm}}"
ZONE="${3:-${GCE_ZONE:-us-west1-b}}"
LOCAL_DB="${SQLITE_DB_PATH:-$HOME/projects/.data/market_data.db}"
REMOTE_DIR="~/projects/.data"
REMOTE_DB="$REMOTE_DIR/market_data.db"
TMP_BACKUP="/tmp/market_data_sync_$$.db"

cleanup() {
    rm -f "$TMP_BACKUP"
}
trap cleanup EXIT

if [[ "$ACTION" != "push" && "$ACTION" != "pull" ]]; then
    echo "Usage: $0 <push|pull> [VM_NAME (default: market-data-vm)] [ZONE (default: us-west1-b)]"
    exit 1
fi

if [ "$ACTION" = "push" ]; then
    if [ ! -f "$LOCAL_DB" ]; then
        echo "Error: Local database not found at $LOCAL_DB"
        exit 1
    fi

    echo "Creating atomic SQLite backup of $LOCAL_DB..."
    sqlite3 "$LOCAL_DB" ".backup '$TMP_BACKUP'"

    echo "Ensuring remote directory $REMOTE_DIR exists on $VM_NAME ($ZONE)..."
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="mkdir -p $REMOTE_DIR"

    echo "Uploading database to $VM_NAME:$REMOTE_DB..."
    gcloud compute scp --compress "$TMP_BACKUP" "$VM_NAME:$REMOTE_DB" --zone="$ZONE"

    echo "Verifying remote database integrity..."
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="sqlite3 $REMOTE_DB 'PRAGMA integrity_check;'"
    echo "Push complete!"

elif [ "$ACTION" = "pull" ]; then
    mkdir -p "$(dirname "$LOCAL_DB")"

    echo "Creating atomic backup on remote VM $VM_NAME ($ZONE) and downloading..."
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="sqlite3 $REMOTE_DB \".backup '/tmp/market_data_remote_backup.db'\""
    gcloud compute scp --compress "$VM_NAME:/tmp/market_data_remote_backup.db" "$TMP_BACKUP" --zone="$ZONE"
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="rm -f /tmp/market_data_remote_backup.db"

    echo "Verifying downloaded database integrity..."
    INTEGRITY="$(sqlite3 "$TMP_BACKUP" 'PRAGMA integrity_check;')"
    if [ "$INTEGRITY" != "ok" ]; then
        echo "Error: Downloaded database failed integrity check: $INTEGRITY"
        exit 1
    fi

    mv "$TMP_BACKUP" "$LOCAL_DB"
    echo "Pull complete! Updated $LOCAL_DB"
fi

