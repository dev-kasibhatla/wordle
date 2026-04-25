# Contributing

Thank you. These are the rules.

## Getting started

```bash
git clone <repo-url>
cd wordle
uv sync
uv pip install -e .
```

## Before submitting

1. All tests must pass.

   ```bash
   uv run pytest -m "not slow"
   ```

2. Slow tests must pass if you touch solver or batch code.

   ```bash
   uv run pytest
   ```

3. Keep changes focused. One logical change per PR.

## Code style

- Pure functions. No hidden state.
- Typed dataclasses or Pydantic models for public contracts.
- Validate at the boundary. Return explicit error codes.
- No print statements in library code. Use return values.
- Docstrings are optional. Keep to one sentence if you write one.

## Solver changes

Rerun the full batch for both modes and include updated solve-rate numbers in the PR.

```bash
uv run wordle-batch --mode a
uv run wordle-batch --mode b
```

## Data changes

Do not add words to `data/5-letter-words.txt` or `data/wordle-test-dataset.csv` without a clear, verifiable source. Run `uv run wordle-check-dataset` to verify consistency.

## Pull requests

- Use a descriptive title. No "fix stuff".
- Write a short description of what changed and why.
- Reference any issue numbers.
