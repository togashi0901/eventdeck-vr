.PHONY: up down build test lint migrate revision psql seed logs fmt \
        prod-up prod-down prod-logs backup

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

# テスト: テスト用DBの作成・破棄込みで pytest を実行
test:
	docker compose exec api pytest

lint:
	docker compose exec api ruff check app tests
	docker compose exec front sh -c "npm run lint"

fmt:
	docker compose exec api ruff format app tests

# Alembic
migrate:
	docker compose exec api alembic upgrade head

revision:
	docker compose exec api alembic revision -m "$(m)"

psql:
	docker compose exec db psql -U eventdeck -d eventdeck

# シードデータ (M1 で実装)
seed:
	docker compose exec api python -m app.seed

# --- 本番/デモ (docker-compose.prod.yml) ---
prod-up:
	docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f

prod-seed:
	docker compose -f docker-compose.prod.yml exec api python -m app.seed

backup:
	./scripts/backup.sh
