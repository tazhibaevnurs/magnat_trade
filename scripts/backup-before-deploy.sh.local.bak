#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TIMESTAMP="$(date +%F_%H-%M-%S)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
mkdir -p "$BACKUP_DIR"

echo "[backup] ensuring db service is running..."
docker compose up -d db >/dev/null

for i in $(seq 1 30); do
  if docker compose exec -T db sh -lc 'export PGPASSWORD="$POSTGRES_PASSWORD"; pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1'; then
    break
  fi
  echo "[backup] waiting for postgres... ($i/30)"
  sleep 2
done
docker compose exec -T db sh -lc 'export PGPASSWORD="$POSTGRES_PASSWORD"; pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1' || {
  echo "[backup] postgres is not ready after timeout"
  exit 1
}

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
