.PHONY: help install install-dev lint format type-check test test-coverage clean all dev compose-up compose-down compose-logs compose-build compose-migrate compose-clean compose-restart

# Default target - show help
help:
	@echo "Software Planner - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install all dependencies including dev tools"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run all linters (flake8, black --check, isort --check)"
	@echo "  make format           Auto-format code with black and isort"
	@echo "  make type-check       Run mypy type checker"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run pytest tests"
	@echo "  make test-coverage    Run tests with coverage report"
	@echo ""
	@echo "Combined:"
	@echo "  make all              Run lint, type-check, and test in sequence"
	@echo "  make dev              Run format, then all checks and tests"
	@echo ""
	@echo "Docker Compose:"
	@echo "  make compose-up       Start all services (API + database)"
	@echo "  make compose-down     Stop all services"
	@echo "  make compose-logs     View service logs (use CTRL+C to exit)"
	@echo "  make compose-build    Rebuild containers from scratch"
	@echo "  make compose-migrate  Run database migrations in running container"
	@echo "  make compose-restart  Restart all services"
	@echo "  make compose-clean    Stop services and remove volumes (deletes data!)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove build artifacts and cache files"

# Install production dependencies
install:
	pip install -r requirements.txt

# Install all dependencies including dev tools
install-dev:
	pip install -r requirements.txt

# Run all linting checks (fail on any error)
lint:
	@echo "Running flake8..."
	flake8 app tests --config=.flake8 || exit 1
	@echo ""
	@echo "Checking code formatting with black..."
	black --check app tests || exit 1
	@echo ""
	@echo "Checking import ordering with isort..."
	isort --check-only app tests || exit 1
	@echo ""
	@echo "✓ All linting checks passed"

# Auto-format code
format:
	@echo "Formatting code with black..."
	black app tests
	@echo ""
	@echo "Sorting imports with isort..."
	isort app tests
	@echo ""
	@echo "✓ Code formatted successfully"

# Run type checking
type-check:
	@echo "Running mypy type checker..."
	@echo "Note: Type checking is currently informational and does not block CI"
	-mypy app tests || true
	@echo ""
	@echo "✓ Type checking completed (errors are informational)"

# Run tests
test:
	@echo "Running pytest..."
	pytest || exit 1
	@echo ""
	@echo "✓ All tests passed"

# Run tests with coverage
test-coverage:
	@echo "Running pytest with coverage..."
	coverage run -m pytest || exit 1
	@echo ""
	coverage report
	@echo ""
	@echo "✓ Tests with coverage completed"

# Run all checks (lint, type-check, test)
all: lint type-check test
	@echo ""
	@echo "✓✓✓ All checks passed! ✓✓✓"

# Development workflow: format then run all checks
dev: format all

# Clean up build artifacts and cache
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleanup complete"

# ============================================================================
# Docker Compose Commands
# ============================================================================

# Start all services (API + database) in detached mode
compose-up:
	@echo "Starting Software Planner services..."
	@if [ ! -f .env ]; then \
		echo "⚠ WARNING: .env file not found. Creating from .env.example..."; \
		cp .env.example .env; \
		echo "✓ Created .env file. Please edit it to set LLM_API_KEY and other required variables."; \
		echo ""; \
	fi
	docker-compose up -d
	@echo ""
	@echo "✓ Services started successfully!"
	@echo ""
	@echo "API available at: http://localhost:8000"
	@echo "Health check: http://localhost:8000/health"
	@echo "API docs: http://localhost:8000/api/v1/docs"
	@echo ""
	@echo "View logs with: make compose-logs"
	@echo "Stop services with: make compose-down"

# Stop all services
compose-down:
	@echo "Stopping Software Planner services..."
	docker-compose down
	@echo "✓ Services stopped"

# View service logs (follow mode)
compose-logs:
	@echo "Showing service logs (press CTRL+C to exit)..."
	@echo ""
	docker-compose logs -f

# Rebuild containers from scratch
compose-build:
	@echo "Rebuilding containers..."
	docker-compose build --no-cache
	@echo "✓ Containers rebuilt successfully"

# Run database migrations in the running app container
compose-migrate:
	@echo "Running database migrations..."
	docker-compose exec app alembic upgrade head
	@echo "✓ Migrations completed"

# Restart all services
compose-restart:
	@echo "Restarting services..."
	docker-compose restart
	@echo "✓ Services restarted"

# Stop services and remove volumes (WARNING: deletes all data!)
compose-clean:
	@echo "⚠ WARNING: This will delete all database data!"
	@echo "Press CTRL+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	@echo "Stopping services and removing volumes..."
	docker-compose down -v
	@echo "✓ Services stopped and volumes removed"
	@echo ""
	@echo "To start fresh, run: make compose-up"
