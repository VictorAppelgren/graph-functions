# SAGA Graph Development Tasks
# Requires: make, python 3.12+, virtual environment activated

.PHONY: help install typecheck typecheck-strict format lint test clean pre-commit

# Default target
help:
	@echo "🎯 SAGA Graph Development Commands"
	@echo "=================================="
	@echo ""
	@echo "Setup:"
	@echo "  install         Install dependencies and setup environment"
	@echo "  install-dev     Install with development dependencies"
	@echo ""  
	@echo "Type Checking:"
	@echo "  typecheck       Run MyPy type checking (standard)"
	@echo "  typecheck-strict Run MyPy with strictest settings"
	@echo ""
	@echo "Code Quality:"
	@echo "  format          Format code with Black and isort"
	@echo "  lint            Run flake8 linting"
	@echo "  pre-commit      Run all pre-commit hooks"
	@echo ""
	@echo "Testing:"
	@echo "  test            Run basic connectivity tests"
	@echo "  test-report     Generate sample PDF report"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean           Clean cache files and temp directories"
	@echo ""
	@echo "💡 All commands assume virtual environment is activated"

# Installation
install:
	@echo "📦 Installing core dependencies..."
	pip install -e .

install-dev:
	@echo "📦 Installing development dependencies..."
	pip install -e ".[dev]"
	pre-commit install

# Type checking
typecheck:
	@echo "🔍 Running MyPy type checking..."
	python scripts/typecheck.py

typecheck-strict:
	@echo "🔍 Running MyPy with strictest settings..."
	mypy --config-file=mypy.ini --strict --show-error-codes graph_db/ utils/ main.py

typecheck-watch:
	@echo "🔍 Running MyPy in watch mode..."
	mypy --follow-imports=silent --ignore-missing-imports --show-error-codes graph_db/ utils/ main.py
	@echo "Watching for changes... (Ctrl+C to stop)"

# Code formatting and linting
format:
	@echo "🎨 Formatting code with Black..."
	black --line-length=100 .
	@echo "📁 Sorting imports with isort..."
	isort --profile black --line-length=100 .

lint:
	@echo "🔍 Running flake8 linting..."
	flake8 --max-line-length=100 --extend-ignore=E203,W503 .

# Pre-commit hooks
pre-commit:
	@echo "🔗 Running all pre-commit hooks..."
	pre-commit run --all-files

pre-commit-install:
	@echo "🔗 Installing pre-commit hooks..."
	pre-commit install

# Testing
test:
	@echo "🧪 Running basic connectivity tests..."
	python -c "from graph_db.db_driver import run_cypher; print('Neo4j:', run_cypher('RETURN 1 AS ok'))"
	python -c "from model_config import get_simple_llm; print('LLM:', get_simple_llm().invoke('ping')[:50])"

test-report:
	@echo "📊 Generating sample PDF report..."
	python Reports/export_asset_analysis_pdf.py

# Maintenance
clean:
	@echo "🧹 Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	find . -name "*~" -delete 2>/dev/null || true

# Development workflow
dev-setup: install-dev pre-commit-install
	@echo "✅ Development environment ready!"
	@echo "Run 'make typecheck' to verify everything is working"

# Quick check for CI/CD
check-all: typecheck lint test
	@echo "✅ All checks passed!"