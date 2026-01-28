.PHONY: up down demo test eval lint logs shell clean build rebuild

# Default target
.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start all services
	docker compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	@echo "Services are up! API available at http://localhost:8000"

down: ## Stop all services
	docker compose down

build: ## Build Docker images
	docker compose build

rebuild: ## Rebuild Docker images (no cache)
	docker compose build --no-cache

logs: ## Tail service logs
	docker compose logs -f

logs-api: ## Tail API logs
	docker compose logs -f api

logs-worker: ## Tail worker logs
	docker compose logs -f worker

shell: ## Shell into API container
	docker compose exec api bash

shell-db: ## Shell into database
	docker compose exec db psql -U labassistant -d labassistant

demo: up ## Run demo requests
	@echo "\n=== Submitting a lab request ==="
	@curl -s -X POST http://localhost:8000/requests \
		-H "Content-Type: application/json" \
		-d '{"text": "How do I handle a database connection timeout?", "priority": "high"}' | python3 -m json.tool
	@echo "\n=== Waiting for processing... ==="
	@sleep 3
	@echo "\n=== Submitting another request ==="
	@curl -s -X POST http://localhost:8000/requests \
		-H "Content-Type: application/json" \
		-d '{"text": "Show me recent critical incidents", "priority": "normal"}' | python3 -m json.tool
	@echo "\n=== Check status with: curl http://localhost:8000/requests/{request_id} ==="

demo-full: up ## Run full demo with status check
	@echo "\n=== Submitting a lab request ==="
	@REQUEST_ID=$$(curl -s -X POST http://localhost:8000/requests \
		-H "Content-Type: application/json" \
		-d '{"text": "How do I handle a database connection timeout?", "priority": "high"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['request_id'])") && \
	echo "Request ID: $$REQUEST_ID" && \
	echo "\n=== Waiting for processing... ===" && \
	sleep 5 && \
	echo "\n=== Checking status ===" && \
	curl -s "http://localhost:8000/requests/$$REQUEST_ID" | python3 -m json.tool

test: ## Run pytest (requires services to be up)
	docker compose exec api pytest tests/ -v --tb=short

test-local: ## Run pytest locally
	pytest tests/ -v --tb=short

eval: ## Run evaluation harness
	docker compose exec api python -m eval.run_eval

eval-local: ## Run evaluation locally
	python -m eval.run_eval

lint: ## Run ruff linter
	ruff check api/ worker/ tests/ eval/

lint-fix: ## Run ruff linter with auto-fix
	ruff check api/ worker/ tests/ eval/ --fix

format: ## Format code with ruff
	ruff format api/ worker/ tests/ eval/

clean: ## Remove volumes and images
	docker compose down -v --rmi local
	rm -rf __pycache__ .pytest_cache .coverage htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

health: ## Check service health
	@echo "API: $$(curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo 'Not running')"
	@echo "Redis: $$(docker compose exec -T redis redis-cli ping 2>/dev/null || echo 'Not running')"
	@echo "Postgres: $$(docker compose exec -T db pg_isready -U labassistant 2>/dev/null || echo 'Not running')"

ci: lint test eval ## Run full CI pipeline locally
