#!/bin/bash
# Admin DB access from bastion via Cloud SQL Auth Proxy + Secret Manager.
set -euo pipefail

PROJECT="${PROJECT:-asanclip-rag-prod}"
INSTANCE="${INSTANCE:-asanclip-db-prod}"
REGION="${REGION:-europe-west1}"
SECRET="${SECRET:-database-url}"
PROXY_PORT="${PROXY_PORT:-54321}"
PROXY_BIN="${PROXY_BIN:-/usr/local/bin/cloud-sql-proxy}"

if ! command -v psql >/dev/null 2>&1; then
  echo "Install postgresql-client first." >&2
  exit 1
fi

if ! command -v "$PROXY_BIN" >/dev/null 2>&1; then
  echo "Install cloud-sql-proxy at $PROXY_BIN first." >&2
  exit 1
fi

TOKEN=$(curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -sf -H "Authorization: Bearer ${TOKEN}" \
  "https://secretmanager.googleapis.com/v1/projects/${PROJECT}/secrets/${SECRET}/versions/latest:access" \
  -o /tmp/asanclip-database-url.json

read -r DB_USER DB_PASS DB_NAME <<EOF
$(python3 <<'PY'
import json, base64, re
from urllib.parse import unquote
raw = base64.b64decode(json.load(open("/tmp/asanclip-database-url.json"))["payload"]["data"]).decode()
m = re.match(r"postgresql(?:\+[^:]+)?://([^:]+):([^@]+)@/?([^?]+)", raw)
if not m:
    raise SystemExit("Could not parse database-url secret")
print(m.group(1), unquote(m.group(2)), m.group(3))
PY
)
EOF

if ! pgrep -f "cloud-sql-proxy.*${INSTANCE}" >/dev/null 2>&1; then
  nohup "$PROXY_BIN" "${PROJECT}:${REGION}:${INSTANCE}" \
    --private-ip --address 127.0.0.1 --port "${PROXY_PORT}" \
    >/tmp/cloud-sql-proxy.log 2>&1 &
  sleep 3
fi

export PGPASSWORD="$DB_PASS"
exec psql -h 127.0.0.1 -p "${PROXY_PORT}" -U "${DB_USER}" -d "${DB_NAME}" "$@"
