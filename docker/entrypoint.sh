#!/bin/sh
set -e

if [ "${RUN_DB_INIT_ON_START:-false}" = "true" ]; then
    echo "==> Initializing database..."
    python scripts/init_db.py
else
    echo "==> Skipping database initialization (RUN_DB_INIT_ON_START=false)"
fi

echo "==> Starting application..."
exec "$@"
