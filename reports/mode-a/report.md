# Wordle Solver Report Mode A (Investigation + Hail-Mary)

Tested on 2316 official Wordle answers.

---

## Summary

| Metric | Value |
|---|---|
| Total puzzles | 2316 |
| Solved | 2316 |
| Failed | 0 |
| Solve rate | 100.0% |
| Average turns (solved) | 3.70 |
| Median turns (solved) | 4.0 |
| 90th percentile turns | 5.0 |

## Solve Rate

![Solve Rate](graphs/solve_rate.png)

Mode A learns letters in the first 3 turns, then picks the best candidate. Discover fast, then commit.

## Turns Distribution

![Turns Distribution](graphs/turns_histogram.png)

Each bar shows how many puzzles were solved in that many turns. Anything beyond turn 6 is a failure.

