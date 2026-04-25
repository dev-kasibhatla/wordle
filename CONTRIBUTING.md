# Contributing

Thank you for your interest. These are the rules.

## Getting started

```bash
git clone <repo-url>
cd wordle
uv sync
uv pip install -e .
```

## Before you submit

1. All tests must pass.

   ```bash
   uv run pytest -m "not slow"
   ```

2. Slow tests must pass if your change touches the solver or batch pipeline.

   ```bash
   uv run pytest
   ```

3. Keep changes focused. One logical change per pull request.

## Code style

- Pure functions where possible. No hidden state.
- Typed dataclasses or Pydantic models for all public contracts.
- Validate at the boundary. Return explicit error codes, never silent failures.
- No print statements in library code. Use return values.
- Docstrings are optional. If you write one, keep it to one sentence.

## Solver changes

If you change solver logic, re-run the full batch for both modes and include updated solve-rate numbers in your PR description.

```bash
uv run wordle-batch --mode a
uv run wordle-batch --mode b
```

## Adding words

Do not add words to `data/5-letter-words.txt` or `data/wordle-test-dataset.csv` without a clear, verifiable source. Run `uv run wordle-check-dataset` to confirm consistency after any data change.

## Pull requests

- Use a descriptive title. No "fix stuff" or "update code".
- Include a short description of what changed and why.
- Reference any relevant issue numbers.
