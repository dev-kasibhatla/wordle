# I Built a Wordle Solver in a Day — and It's Almost Perfect

*~2 min read*

---

I needed to turn my brain off.

Not sleep. Not scroll. Just build something — something small, self-contained, and a little bit silly. So I picked Wordle. A five-letter word. Six attempts. Billions of people have played it. I wanted to see if a computer could beat it every time, and how fast.

One day later, here's what I made.

---

## The Web App

There are three tabs. Each does one thing well.

---

### Play

A clean, full Wordle game. Type your guesses, use the on-screen keyboard, share your result. Nothing extra.

<!-- screenshot: Play tab -->
![Play tab](screenshots/play.png)

---

### Auto Solve

Type any five-letter word as the secret. Pick an algorithm. Watch the solver guess it step by step — coloured tiles and all.

<!-- screenshot: Auto Solve tab -->
![Auto Solve tab](screenshots/autosolve.png)

---

### Solver

Already mid-game? Enter your guesses and scores tile by tile. The solver reads your board and tells you the best next word to play.

<!-- screenshot: Solver tab -->
![Solver tab](screenshots/solver.png)

---

## Three Algorithms

I wrote three solving strategies, each with a different philosophy. All were tested against all **2,316 official Wordle answers**.

---

### Mode A — Investigate + Hail Mary

The solver spends its first few guesses gathering information — words chosen purely to expose as many unknown letters as possible, regardless of whether they could be the answer. Once it has enough data, it switches to only guessing real candidates.

| Metric | Result |
|---|---|
| Solve rate | **100%** |
| Average turns | **3.70** |
| Worst case | 6 turns |

---

### Mode B — Hail Mary Only

Every guess is a real candidate from the answer list. No warmup, no information gathering — just pure elimination from the start. Simpler, but harder.

| Metric | Result |
|---|---|
| Solve rate | **72.5%** |
| Average turns | **4.86** (among solved) |
| Worst case | 6 turns |

Mode B shows why pure guessing without a strategy fails. More than a quarter of puzzles run out of turns.

---

### Mode C — Entropy-Optimal

This one does the maths. Before every guess it scores every word in a 12,000-word pool by how much information it would reveal, then picks the highest. The opener (`crate`) and the next two moves are pre-computed offline so the app stays fast.

| Metric | Result |
|---|---|
| Solve rate | **100%** |
| Average turns | **3.43** |
| Solved in 3 turns | **53%** of all puzzles |
| Worst case | 6 turns (1 puzzle) |

3.43 average. That is close to the theoretical limit.

---

## Everything Is Free

The web app is live and free to use. The full source code is open source on GitHub — game engine, all three solvers, the API, the batch runner that generated these results, and the test suite.

No ads. No accounts. No tracking.

[→ Play the game](/)  
[→ Source code on GitHub](https://github.com/dev-kasibhatla/wordle)

---

*Built in one day, for no reason other than it was fun.*
