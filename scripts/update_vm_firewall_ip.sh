#!/bin/bash
set -euo pipefail

# Updates the GCP 'allow-dashboard-5001' firewall rule to match your current public IP
PROJECT_ID="${GCE_PROJECT:-market-data-vm-pm2026}"
RULE_NAME="allow-dashboard-5001"

CURRENT_IP="$(curl -s https://ifconfig.me || curl -s https://api.ipify.org)"
if [ -z "$CURRENT_IP" ]; then
    echo "Error: Could not determine current public IP."
    exit 1
fi

echo "Updating firewall rule '$RULE_NAME' in project '$PROJECT_ID' to allow $CURRENT_IP/32..."
gcloud compute firewall-rules update "$RULE_NAME" \
  --project="$PROJECT_ID" \
  --source-ranges="$CURRENT_IP/32" \
  --quiet

echo "Done! Port 5001 is now open for $CURRENT_IP/32."

