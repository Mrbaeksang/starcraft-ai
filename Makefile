EXTRA ?= cpu
UV_RUN := uv run --extra $(EXTRA)

.PHONY: setup doctor smoke test lint format check

setup:
	uv sync --extra $(EXTRA) --group dev

doctor:
	$(UV_RUN) scai doctor

smoke:
	$(UV_RUN) scai smoke-train --steps 50 --device auto

test:
	$(UV_RUN) pytest -q

lint:
	$(UV_RUN) ruff check .

format:
	$(UV_RUN) ruff format .

check: lint test smoke
