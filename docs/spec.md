# System Spec

## Scope
- Wordle rules engine with strict feedback semantics.
- One endpoint: `POST /wordle/play`.
- Solver with `investigate` and `hail_mary` modes.
- Async batch runner for official answer corpus.

## Wordle Rules Enforced
- Guess length must be exactly 5.
- Guess must exist in the allowed dictionary.
- Maximum turns is 6.
- Feedback per position uses numeric encoding:
  - `2`: letter and position are correct.
  - `1`: letter exists but wrong position.
  - `0`: letter is not present given remaining letter counts.
- Duplicate letters are scored with two-pass accounting identical to Wordle.

## API
### `POST /wordle/play`
Supports two actions through one contract.

Request:
- `action`: `"new"` or `"guess"`
- `game_id`: required for `guess`
- `guess`: required for `guess`

Response:
- `game_id`
- `status`: `in_progress | solved | failed`
- `turn`
- `turns_remaining`
- `history`: list of `{guess, score}`
- `latest`: latest history item or null
- `error`: optional structured error object

## Solver Behavior
- Investigate mode tries high-information words with mostly unique letters.
- It runs up to 3 turns unless thresholds trigger earlier switch.
- Hail Mary mode applies all known constraints to fit candidate answers.
- Turn 4 and later always use hail mary mode.
- Solver result includes:
  - `words_tried`
  - `turns_taken`
  - `solved`

## Batch Outputs
Reports are written to `reports/`:
- `results.json`: per-puzzle outcomes.
- `summary.json`: aggregate metrics and histograms.
