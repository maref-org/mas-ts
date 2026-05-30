# Contributing to MAS-TS-001 Evaluation Harness

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov
```

## Running Tests

```bash
pytest tests/ -v --cov=.
```

## Code Style

- Python 3.11+
- Use `logging` (not `print()`) for diagnostic output
- Add `--version` flag to all CLI entry points
- Handle `json.JSONDecodeError` for all JSON file reads

## Before Submitting

1. All tests pass: `pytest tests/ -v`
2. No syntax errors: `python -c "import ast; ast.parse(open('your_file.py').read())"`
