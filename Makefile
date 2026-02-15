.PHONY: local-up local-down local-logs local-logs-all local-rebuild local-health local-shell local-db

local-up:
	docker compose up -d --build

local-down:
	docker compose down

local-logs:
	docker compose logs -f backend

local-logs-all:
	docker compose logs -f

local-rebuild:
	docker compose down
	docker compose up -d --build

local-health:
	@echo "Checking backend health..."
	@curl -s http://localhost:8000/api/v1/health/live | python -m json.tool 2>/dev/null || echo "Backend not ready"

local-shell:
	docker compose exec backend bash

local-db:
	docker compose exec postgres psql -U instantrisk_admin -d instantrisk

local-status:
	docker compose ps
