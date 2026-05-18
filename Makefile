.PHONY: help install test build clean publish publish-test lint

POETRY ?= poetry

help:
	@echo "Common targets:"
	@echo "  make install       - Install project and dev dependencies"
	@echo "  make test          - Run test suite"
	@echo "  make build         - Build wheel and sdist"
	@echo "  make clean         - Remove build and cache artifacts"
	@echo "  make lint          - Run linting and format code (ruff)"
	@echo "  make publish-test  - Publish to TestPyPI"
	@echo "  make publish       - Publish to PyPI"

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
	$(POETRY) run ruff check --fix --unsafe-fixes logcraft tests
	$(POETRY) run ruff format logcraft tests

publish-test:
	$(POETRY) build
	$(POETRY) publish --repository testpypi

publish:
	$(POETRY) build
	$(POETRY) publish
