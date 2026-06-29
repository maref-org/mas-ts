# Contributing to MAS-TS-001 Evaluation Harness

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[ml,dev]"
```

## Running Tests

```bash
pytest tests/ -v --cov=mas_eval --cov-fail-under=85
mypy mas_eval/ --strict --ignore-missing-imports
ruff check mas_eval/
```

## Code Style

- Python 3.11+
- Type annotations required on all function signatures (mypy strict)
- Use standard library types: `dict`, `list`, `tuple`, `bool`, `float`, `int`, `str`, `None`
- Use `|` for union types: `str | None` not `Optional[str]`
- Use `logging` (not `print()`) for diagnostic output
- Add `--version` flag to all CLI entry points
- Handle `json.JSONDecodeError` for all JSON file reads

## Before Submitting

1. All tests pass: `pytest tests/ -v`
2. Type check: `mypy mas_eval/ --strict --ignore-missing-imports`
3. Lint clean: `ruff check mas_eval/`
4. Coverage ≥ 85%: `pytest --cov=mas_eval --cov-fail-under=85`

## License

By contributing to this project, you agree that your contributions will be licensed under the Apache License, Version 2.0.
