.PHONY: help install test build clean publish publish-test lint format fix check

POETRY ?= poetry

help:
	@echo "Common targets:"
	@echo "  make install       - Install project and dev dependencies"
	@echo "  make test          - Run test suite"
	@echo "  make build         - Build wheel and sdist"
	@echo "  make clean         - Remove build and cache artifacts"
	@echo "  make publish-test  - Publish to TestPyPI"
	@echo "  make publish       - Publish to PyPI"
	@echo ""
	@echo "Code quality targets:"
	@echo "  make lint          - Run linting checks (ruff)"
	@echo "  make format        - Format code (ruff format)"
	@echo "  make fix           - Auto-fix linting issues"
	@echo "  make check         - Run all checks (lint + test)"

install:
	$(POETRY) install

test:
	$(POETRY) run pytest -q

build:
	$(POETRY) build

clean:
	rm -rf build dist .pytest_cache __pycache__ .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

lint:
	$(POETRY) run ruff check logcraft tests

format:
	$(POETRY) run ruff format logcraft tests

fix:
	$(POETRY) run ruff check --fix logcraft tests
	$(POETRY) run ruff format logcraft tests

check: lint test
	@echo "All checks passed!"

publish-test:
	$(POETRY) build
	$(POETRY) publish --repository testpypi

publish:
	$(POETRY) build
	$(POETRY) publish
