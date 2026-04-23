#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TIMESTAMP="$(date +%F_%H-%M-%S)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
mkdir -p "$BACKUP_DIR"

echo "[backup] ensuring db service is running..."
docker compose up -d db >/dev/null

OUT_FILE="$BACKUP_DIR/postgres_${TIMESTAMP}.dump"
echo "[backup] writing $OUT_FILE"

docker compose exec -T db sh -lc '
  export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
  pg_dump \
    -h 127.0.0.1 \
    -U "${POSTGRES_USER:?POSTGRES_USER is required}" \
    -d "${POSTGRES_DB:?POSTGRES_DB is required}" \
    -Fc
' > "$OUT_FILE"

echo "[backup] done: $OUT_FILE"
