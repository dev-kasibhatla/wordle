# Wordle

A complete Wordle engine. Game logic, solver, API, and evaluation tools.

---

## What is this

Wordle is a word-guessing game. Six attempts to find a five-letter word. Each guess is scored:

- **2**: correct letter, correct position (green)
- **1**: correct letter, wrong position (yellow)
- **0**: letter not in word (grey)

Includes a game engine, two solver modes, an HTTP API, and batch evaluation across 2 315 official Wordle answers.

---

## Project structure

```
src/wordle/
  engine.py          scoring logic
  game.py            game session
  data.py            word lists
  constants.py       paths and limits
  errors.py          error codes
  service.py         game service
  api/
    app.py           FastAPI app
    schemas.py       request/response types
  solver/
    constraints.py   constraint tracking
    strategy.py      solver modes
  batch/
    runner.py        batch evaluator
    metrics.py       statistics
    report.py        markdown and graphs
data/
  5-letter-words.txt guess dictionary
  wordle-test-dataset.csv official answers
reports/
  mode-a/  investigation + hail-mary results
  mode-b/  hail-mary only results
tests/  pytest suite
docs/   spec and standards
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
```

FastAPI server at `http://localhost:8000`. Docs at `/docs`.

Static pages:

- `/terms`
- `/privacy`
- `/faqs`
- `/changelog`

**Endpoints**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/games` | Create game |
| `POST` | `/games/{game_id}/guesses` | Submit guess |
| `GET` | `/games/{game_id}` | Get state |

### Batch evaluator

Run solver against all official answers and generate reports.

```bash
# Mode A: investigation + hail-mary (default)
uv run wordle-batch --mode a --concurrency 16

# Mode B: hail-mary only
uv run wordle-batch --mode b --concurrency 16
```

Results in `reports/mode-a/` or `reports/mode-b/`.

### Dataset consistency check

```bash
uv run wordle-check-dataset
```

Verifies every official answer appears in the guess dictionary.

---

## Engine

`engine.py` has one pure function:

```python
from wordle.engine import score_guess

score_guess("crane", "cigar")  # [2, 0, 0, 1, 0]
```

Duplicate letters are scored exactly: marked green or yellow only as many times as they appear in the secret. Extras score 0.

`game.py` wraps the engine with state, turn limits, validation, and history.

---

## Solver

The solver lives in `src/wordle/solver/`. It takes the full guess dictionary and the set of valid answers, applies letter constraints after every guess, and returns the words tried, turns taken, and a trace of which mode each turn used.

### Mode A: Investigation + Hail-Mary

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

### Mode B: Hail-Mary Only

```python
config = SolverConfig(mode="b")
result = solve_secret("crane", guess_words, answer_words, config=config)
```

Every guess is the best candidate from turn 1. No discovery. Fast when lucky. Narrow margin for error.

**Results on 2 315 official puzzles:** 97.49% solve, 4.27 avg turns.

---

## Reports

Each batch run writes to its report directory:

| File | Contents |
|---|---|
| `results.json` | Per-puzzle outcome and traces |
| `summary.json` | Stats: rate, histogram, averages, failures |
| `report.md` | Summary with embedded graphs |
| `graphs/turns_histogram.png` | Turns distribution |
| `graphs/solve_rate.png` | Solved vs failed |

---

## Data

`data/5-letter-words.txt`: 12 972 valid five-letter words.

`data/wordle-test-dataset.csv`: 2 315 official Wordle answers.

All answers exist in the guess dictionary (verified by `wordle-check-dataset`).

---

## Tests

```bash
# Fast tests only
uv run pytest -m "not slow"

# Full suite with batch run
uv run pytest

# Hail-mary suite only
uv run pytest tests/test_hail_mary.py -m slow -v
```

Test layers:

| File | Covers |
|---|---|
| `test_engine.py` | Scoring and duplicates |
| `test_solver.py` | Modes and constraints |
| `test_batch.py` | Batch runner and reports |
| `test_hail_mary.py` | Mode-B validation |
| `test_api.py` | REST endpoints |
| `test_dataset_consistency.py` | Data integrity |

## Deployment

The public deployment follows the same shape as Mockasi: predeploy checks, Docker build and export, remote upload, container replacement, and postdeploy validation.

```bash
# local validation + image export
bash scripts/predeploy_check.sh

# full remote deployment
bash scripts/deploy_pipeline.sh user@server https://wordle.example.com /opt/wordle 8000
```

For public hosting, keep hostnames, SSH credentials, registry credentials, and base URLs in GitHub Actions secrets or an untracked `.env.production` on the server. Do not commit deploy values into the repo.

Release flow:

```bash
bash scripts/release.sh patch
```

That refreshes `static/changelog.html` from git history before tagging and publishing.

### Multi-Architecture Support

Wordle builds separate Docker images for amd64 and arm64 during release:

- `wordle:0.x.y` – amd64 image (default for most servers)
- `wordle:0.x.y-arm64` – arm64 image (for ARM hosts like Apple Silicon, Raspberry Pi, Graviton)
- `wordle:latest` – latest amd64
- `wordle:latest-arm64` – latest arm64

**On arm64 hosts**, set the image tag before running docker-compose:

```bash
TAG=latest-arm64 docker-compose up
```

Or edit `docker-compose.yml` to hardcode `image: wordle:latest-arm64` if you always run on ARM.

---

## Docs

- `docs/spec.md` Full engine and API specification
- `docs/standards.md` Coding standards and conventions

---

## Rules

- Validate all inputs at the boundary. Return explicit errors.
- Scoring is pure. No side effects.
- Solver respects immutability.
- Report dirs are created on demand, never auto-cleared.
