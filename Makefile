EXTRA ?= cpu
UV_RUN := uv run --extra $(EXTRA)

.PHONY: setup doctor smoke benchmark test lint format format-check build check

setup:
	uv sync --locked --extra $(EXTRA) --group dev

doctor:
	$(UV_RUN) scai doctor

smoke:
	$(UV_RUN) scai smoke-train --steps 50 --device auto

benchmark:
	$(UV_RUN) scai benchmark-synthetic --profile tiny --steps 50 --device auto

test:
	$(UV_RUN) pytest -q

lint:
	$(UV_RUN) ruff check .

format:
	$(UV_RUN) ruff format .

format-check:
	$(UV_RUN) ruff format --check .

build:
	uv build

check: lint format-check test smoke benchmark build
