# Phalanx build checks. Works from the main checkout and from agent worktrees:
# the shared pinned environment lives at <main repo>/.venv-build (uv.lock).
ROOT := $(abspath $(shell git rev-parse --git-common-dir)/..)
PY ?= $(ROOT)/.venv-build/bin/python

.PHONY: check lint fmt audit test-fast test test-all env contract-docs solution-context

## make check: lint + static determinism audit + all tests except slow/data (the gate every commit must pass)
check: lint audit test-fast

lint:
	$(PY) -I -m ruff check src tests tools
	$(PY) -I -m ruff format --check src tests tools

fmt:
	$(PY) -I -m ruff format src tests tools
	$(PY) -I -m ruff check --fix src tests tools

audit:
	$(PY) -I tools/audit_static.py src

test-fast:
	$(PY) -I -m pytest -q -m "not slow and not data"

## make test: everything except tests needing external data
test:
	$(PY) -I -m pytest -q -m "not data"

## make test-all: everything, including DASHlink-backed tests (data paths from env, read-only)
test-all:
	$(PY) -I -m pytest -q

## make env: (re)create the pinned build environment from uv.lock
env:
	cd $(ROOT) && UV_PROJECT_ENVIRONMENT=.venv-build uv sync --python 3.13 --frozen --all-groups

## make contract-docs: regenerate docs/contract/ (dictionary + contract artefacts); a test fails if it drifts
contract-docs:
	$(PY) -I tools/build_contract_docs.py

## make solution-context: generate solution_context/ on request (downstream kit; not tracked in git, owner 2026-10-15)
solution-context:
	$(PY) -I tools/build_solution_context.py
