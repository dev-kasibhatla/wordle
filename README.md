# Wordle

A complete, modular Wordle engine with a REST API, a two-mode solver, and a batch evaluation pipeline.

---

## What is this

Wordle is a word-guessing game. The player has six attempts to identify a secret five-letter word. After each guess the engine scores every letter:

- **2** — correct letter, correct position (green)
- **1** — correct letter, wrong position (yellow)
- **0** — letter not in the word (grey)

This project ships the game engine, a solver, an HTTP API, and tools to measure solver performance across all 2 315 official Wordle answers.

---

## Project structure

```
src/wordle/
  engine.py          — pure scoring function
  game.py            — stateful game session
  data.py            — word list loader and validator
  constants.py       — shared paths and limits
  errors.py          — typed error codes
  service.py         — game management service
  api/
    app.py           — FastAPI application factory
    schemas.py       — request/response models
  solver/
    constraints.py   — letter constraint tracker
    strategy.py      — two-mode solver logic
  batch/
    runner.py        — async batch evaluator
    metrics.py       — aggregation and statistics
    report.py        — markdown report + PNG graph generation
data/
  5-letter-words.txt         — full guess dictionary
  wordle-test-dataset.csv    — 2 315 official Wordle answers
reports/
  mode-a/            — results for investigation + hail-mary mode
  mode-b/            — results for hail-mary-only mode
tests/               — pytest test suite
docs/                — spec and standards
```

---

## Setup

Requires Python 3.12+ and [uv](https://github.com/astral-sh/uv).

```bash
git clone <repo-url>
cd wordle
uv sync
uv pip install -e .
```

---

## Running

### REST API

```bash
uv run wordle-api
# or
uv run python -m wordle api
```

Starts a FastAPI server at `http://localhost:8000`. Interactive docs at `/docs`.

**Endpoints**

| Method | Path | Description |
|---|---|---|
| `POST` | `/games` | Create a new game session |
| `POST` | `/games/{game_id}/guesses` | Submit a guess |
| `GET` | `/games/{game_id}` | Get current game state |

### Batch evaluator

Runs the solver against all official answers and writes reports.

```bash
# Mode A — investigation + hail mary (default)
uv run wordle-batch --mode a --concurrency 16

# Mode B — hail mary only
uv run wordle-batch --mode b --concurrency 16
```

Results land in `reports/mode-a/` or `reports/mode-b/`.

### Dataset consistency check

```bash
uv run wordle-check-dataset
```

Verifies every official answer appears in the guess dictionary.

---

## Wordle engine

`engine.py` exposes one pure function:

```python
from wordle.engine import score_guess

score_guess("crane", "cigar")  # [2, 0, 0, 1, 0]
```

Duplicate-letter handling is exact: a letter is marked green or yellow only as many times as it appears in the secret. Extra occurrences score 0.

`game.py` wraps the engine in a stateful session that enforces turn limits, validates guess length, and tracks history.

---

## Solver

The solver lives in `src/wordle/solver/`. It takes the full guess dictionary and the set of valid answers, applies letter constraints after every guess, and returns the words tried, turns taken, and a trace of which mode each turn used.

### Mode A — Investigation + Hail Mary

```python
from wordle.solver.strategy import SolverConfig, solve_secret

config = SolverConfig(mode="a")
result = solve_secret("crane", guess_words, answer_words, config=config)
```

**Turn logic:**

1. Turns 1-3 run in *investigation* mode. The solver picks a guess from the full dictionary that maximises unique letter coverage across the current candidate set. The goal is to eliminate letters fast, not to guess the answer directly.
2. After turn 3, or earlier when enough constraints have accumulated (3+ known letters, 2+ locked positions, or 18 or fewer candidates left), the solver switches to *hail mary* and picks the top-ranked surviving candidate.

**Thresholds** are configurable via `SolverConfig`:

| Field | Default | Effect |
|---|---|---|
| `investigate_limit` | 3 | Max turns in investigation mode |
| `threshold_known_letters` | 3 | Switch early if this many letters are known |
| `threshold_locked_positions` | 2 | Switch early if this many positions are fixed |
| `threshold_candidate_count` | 18 | Switch early if candidate pool is this small |

**Results on 2 315 official puzzles:** 98.19% solve rate, 3.76 average turns.

### Mode B — Hail Mary Only

```python
config = SolverConfig(mode="b")
result = solve_secret("crane", guess_words, answer_words, config=config)
```

Every single guess is the highest-ranked surviving candidate from turn 1. No discovery phase. This converges faster when luck is with you but has a narrower margin for error.

**Results on 2 315 official puzzles:** 97.49% solve rate, 4.27 average turns.

---

## Reports

Each batch run writes three files to its report directory:

| File | Contents |
|---|---|
| `results.json` | Per-puzzle outcome: secret, solved, turns, words tried, mode trace |
| `summary.json` | Aggregate stats: solve rate, histogram, average/median/p90 turns, top failures |
| `report.md` | Human-readable summary with embedded PNG graphs |
| `graphs/turns_histogram.png` | Bar chart of turns distribution |
| `graphs/solve_rate.png` | Pie chart of solved vs failed |

---

## Data

`data/5-letter-words.txt` — 12 972 valid five-letter English words used as the guess dictionary.

`data/wordle-test-dataset.csv` — 2 315 official Wordle answers curated from the original NYT puzzle set.

All answers are guaranteed to appear in the guess dictionary (verified by `wordle-check-dataset`).

---

## Tests

```bash
# Fast tests only (< 5 s)
uv run pytest -m "not slow"

# Full suite including hail-mary batch run (~60 s)
uv run pytest

# Hail-mary suite only
uv run pytest tests/test_hail_mary.py -m slow -v
```

Tests are organised by layer:

| File | Coverage |
|---|---|
| `test_engine.py` | Scoring, duplicate-letter rules |
| `test_solver.py` | Solver modes, constraint propagation |
| `test_batch.py` | Batch runner output and report files |
| `test_hail_mary.py` | Full mode-B run, mode trace validation |
| `test_api.py` | REST endpoints |
| `test_dataset_consistency.py` | Answer/dictionary integrity |

---

## Docs

- `docs/spec.md` — full engine and API specification
- `docs/standards.md` — coding standards and conventions

---

## Rules

- All external inputs are validated at the boundary and return explicit error codes.
- The scoring function is pure and has no side effects.
- The solver never mutates shared state.
- Report directories are created on demand and never cleared automatically.
