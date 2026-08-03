#!/bin/bash
set -euo pipefail
TOKEN=$(curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
PASS=$(curl -sf -H "Authorization: Bearer ${TOKEN}" \
  "https://secretmanager.googleapis.com/v1/projects/asanclip-rag-prod/secrets/db-password/versions/latest:access" \
  | python3 -c 'import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)["payload"]["data"]).decode())')
export PGPASSWORD="$PASS"
psql -h 10.220.0.2 -U asanclip_app -d Sale1404 -c "SELECT current_database(), current_user;" -q -t
echo DB_CONNECT_OK
