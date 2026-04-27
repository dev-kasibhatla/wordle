# Wordle Solver Report Mode B (Hail-Mary Only)

Tested on 18783 official Wordle answers.

---

## Summary

| Metric | Value |
|---|---|
| Total puzzles | 18783 |
| Solved | 13620 |
| Failed | 5163 |
| Solve rate | 72.5% |
| Average turns (solved) | 4.86 |
| Median turns (solved) | 5.0 |
| 90th percentile turns | 6.0 |

## Solve Rate

![Solve Rate](graphs/solve_rate.png)

Mode B commits immediately. Every guess is the best candidate. No discovery, no hesitation.

## Turns Distribution

![Turns Distribution](graphs/turns_histogram.png)

Each bar shows how many puzzles were solved in that many turns. Anything beyond turn 6 is a failure.

## Failures (5163 puzzles)

| Secret | Guesses tried |
|---|---|
| `adpao` | aahed → abada → addax → adjag → adlai → adman |
| `adzes` | aahed → adder → adeem → adiel → adnex → advew |
| `agaze` | aahed → abase → acale → agape → agate → agave |
| `agron` | aahed → abbot → accoy → aflow → agios → agrom |
| `aimed` | aahed → abbed → acned → added → agued → ailed |
| `aired` | aahed → abbed → acned → added → agued → ailed |
| `airer` | aahed → abbes → accel → aeger → after → aimer |
| `aiver` | aahed → abbes → accel → aeger → after → aimer |
| `aiyee` | aahed → abbes → accel → aeger → aimee → ainee |
| `akasa` | aahed → abaca → afara → agama → ajaja → akala |

