# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Commands

```bash
# Run tests
pytest

# Run a single test
pytest tests/test_main.py::test_main

# Lint and format
ruff check .
ruff format .

# Run the CLI entry point
my-project
```

## Architecture

- `my_project/` — main package source code
- `tests/` — pytest test suite mirroring the package structure
- Entry point: `my_project/main.py:main`, exposed as the `my-project` CLI command via `pyproject.toml`
- Tooling: `ruff` for linting/formatting, `pytest` for tests, `setuptools` as build backend
