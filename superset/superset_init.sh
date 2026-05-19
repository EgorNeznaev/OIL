#!/bin/bash
set -e

pip install -q psycopg2-binary sqlalchemy 2>/dev/null || true

superset db upgrade
superset fab create-admin \
  --username admin \
  --firstname Admin \
  --lastname User \
  --email admin@oil.local \
  --password admin \
  2>/dev/null || true
superset init

PG_USER="${POSTGRES_USER:-oiluser}"
PG_PASS="${POSTGRES_PASSWORD:-oilpass}"
PG_DB="${POSTGRES_DB:-oildb}"

python <<'PY'
import os
import time

from sqlalchemy import create_engine, text

url = (
    f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@postgres:5432/{os.environ['POSTGRES_DB']}"
)
for _ in range(30):
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("PostgreSQL is ready for Superset connection")
        break
    except Exception:
        time.sleep(2)
PY

exec gunicorn \
  --bind 0.0.0.0:8088 \
  --workers 4 \
  --timeout 120 \
  --limit-request-line 0 \
  --limit-request-field_size 0 \
  "superset.app:create_app()"
