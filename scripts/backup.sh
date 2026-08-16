#!/usr/bin/env bash
# DBバックアップ (M6: 本番デプロイ準備)
# 使い方: ./scripts/backup.sh [compose-file]   (既定: docker-compose.prod.yml)
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE_FILE="${1:-docker-compose.prod.yml}"
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p backups

docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U eventdeck eventdeck | gzip > "backups/eventdeck-$STAMP.sql.gz"

echo "backup written: backups/eventdeck-$STAMP.sql.gz"
# 復元例: gunzip -c backups/eventdeck-XXX.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U eventdeck -d eventdeck
