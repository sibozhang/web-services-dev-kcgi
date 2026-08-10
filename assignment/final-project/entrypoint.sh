#!/bin/sh
set -eu

python - <<'PY'
import os
import time
import psycopg

url = os.environ.get("DATABASE_URL", "")
skip_migrations = os.environ.get("SKIP_DB_MIGRATIONS", "0") == "1"
if url.startswith("postgresql+psycopg://"):
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)
if url.startswith("postgresql://"):
    for attempt in range(120):
        try:
            with psycopg.connect(url) as connection:
                if skip_migrations:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT to_regclass('public.teams')")
                        if cursor.fetchone()[0] is None:
                            raise RuntimeError("database schema is not ready")
                print("Database is ready")
                break
        except (psycopg.OperationalError, RuntimeError):
            if attempt == 119:
                raise
            time.sleep(1)
PY

if [ "${SKIP_DB_MIGRATIONS:-0}" = "1" ]; then
    echo "Skipping database migrations for sidecar process"
else
    flask --app wsgi:app db upgrade
fi

TLS_MODE="${TLS_MODE:-direct}"
TLS_CERT_FILE="${TLS_CERT_FILE:-/tmp/mlb-dugout.crt}"
TLS_KEY_FILE="${TLS_KEY_FILE:-/tmp/mlb-dugout.key}"

if [ "$TLS_MODE" = "direct" ]; then
    python /app/scripts/generate_dev_certificate.py \
        --cert "$TLS_CERT_FILE" \
        --key "$TLS_KEY_FILE"
fi

if [ "$TLS_MODE" = "direct" ] && [ "${1:-}" = "gunicorn" ]; then
    exec "$@" --certfile "$TLS_CERT_FILE" --keyfile "$TLS_KEY_FILE"
fi

exec "$@"
