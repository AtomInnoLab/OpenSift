# Contributing

We welcome contributions to OpenSift! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/AtomInnoLab/OpenSift.git
cd opensift
make dev-setup
```

This installs all dependencies (including dev tools) and sets up pre-commit hooks.

## Code Quality

```bash
make lint          # Run linter (ruff)
make lint-fix      # Auto-fix lint issues
make format        # Format code (ruff)
make typecheck     # Run type checker (mypy)
make check         # Full CI check (lint + format + typecheck + test)
```

## Running Tests

```bash
make test          # All tests
make test-unit     # Unit tests only (fast, no Docker)
make test-integration  # Integration tests (requires Docker)
```

See [Testing](testing.md) for details on integration test setup.

## Project Conventions

- **Python 3.11+** — All code targets Python 3.11 and above
- **Async-first** — All I/O operations use `async/await`
- **Pydantic** — Data models and configuration use Pydantic v2
- **Type hints** — All functions have type annotations (enforced by mypy strict mode)
- **120-char line length** — Configured in ruff

## Pull Request Guidelines

1. Fork the repository and create a feature branch
2. Write tests for new functionality
3. Ensure `make check` passes
4. Submit a PR with a clear description of the changes
