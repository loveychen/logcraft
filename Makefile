.PHONY: help install test build clean publish publish-test

POETRY ?= poetry

help:
	@echo "Common targets:"
	@echo "  make install       - Install project and dev dependencies"
	@echo "  make test          - Run test suite"
	@echo "  make build         - Build wheel and sdist"
	@echo "  make clean         - Remove build and cache artifacts"
	@echo "  make publish-test  - Publish to TestPyPI"
	@echo "  make publish       - Publish to PyPI"

install:
	$(POETRY) install

test:
	$(POETRY) run pytest -q

build:
	$(POETRY) build

clean:
	rm -rf build dist .pytest_cache

publish-test:
	$(POETRY) build
	$(POETRY) publish --repository testpypi

publish:
	$(POETRY) build
	$(POETRY) publish
