.PHONY: help install install-dev lint format type-check test test-coverage clean all dev

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
