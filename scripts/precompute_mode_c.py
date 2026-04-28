#!/usr/bin/env python3
"""Precompute mode C strategy data.

Computes:
1. Best opener (from full guess pool, by entropy against answer words)
2. Best turn-2 response for every opening pattern (from full guess pool)

The output is printed as Python source to paste into strategy.py.

Usage:
    uv run python scripts/precompute_mode_c.py

Runtime: ~3-5 minutes (30M pattern computations, one-time cost).
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from math import log2
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wordle.data import load_wordle_data
from wordle.engine import score_guess


# ── Pattern helpers ────────────────────────────────────────────────────────────

def _pattern_int(guess: str, secret: str) -> int:
    sc = score_guess(secret, guess)
    return sc[0] + 3 * sc[1] + 9 * sc[2] + 27 * sc[3] + 81 * sc[4]


ALL_GREEN = 2 + 6 + 18 + 54 + 162  # = 242


def _entropy(counts: Counter) -> float:
    n = sum(counts.values())
    if n <= 1:
        return 0.0
    h = 0.0
    for c in counts.values():
        p = c / n
        h -= p * log2(p)
    return h


# ── Worker for finding best opener ────────────────────────────────────────────

def _score_opener_batch(args: tuple) -> list[tuple[str, float]]:
    """Score a batch of words as potential openers. Top-level for pickling."""
    words_batch, answer_words = args
    results = []
    for word in words_batch:
        counts: Counter[int] = Counter()
        for secret in answer_words:
            counts[_pattern_int(word, secret)] += 1
        h = _entropy(counts)
        results.append((word, h))
    return results


# ── Worker for computing turn-2 lookup ────────────────────────────────────────

def _compute_turn2_for_pattern(args: tuple) -> tuple[int, str, float]:
    """Find best turn-2 word from full pool for one opening pattern."""
    pattern_int, candidates, guess_words = args
    if not candidates:
        return pattern_int, "", 0.0

    # Score every word in guess pool as potential turn-2 guess
    best_word = ""
    best_score = -1.0
    n = len(candidates)
    candidate_set = set(candidates)

    for word in guess_words:
        counts: Counter[int] = Counter()
        for secret in candidates:
            counts[_pattern_int(word, secret)] += 1

        h = _entropy(counts)

        # Small bonus for being a candidate (can solve directly)
        if word in candidate_set:
            h += 0.5 / n  # tiny tie-breaker favouring answerable guesses

        if h > best_score:
            best_score = h
            best_word = word

    return pattern_int, best_word, best_score


def main() -> None:
    data = load_wordle_data()
    answer_words = list(data.official_answers)
    guess_words = list(data.guess_words)

    print(f"Answer pool: {len(answer_words)}  Guess pool: {len(guess_words)}", flush=True)

    # ── Step 1: Find best opener from full guess pool ──────────────────────────
    print("\n[1/3] Computing opener entropy for all guess words …", flush=True)
    t0 = time.perf_counter()

    batch_size = 500
    batches = [guess_words[i:i + batch_size] for i in range(0, len(guess_words), batch_size)]
    args = [(b, answer_words) for b in batches]

    all_scored: list[tuple[str, float]] = []
    with ProcessPoolExecutor() as pool:
        for result in pool.map(_score_opener_batch, args):
            all_scored.extend(result)

    all_scored.sort(key=lambda x: -x[1])
    elapsed = time.perf_counter() - t0
    print(f"   Done in {elapsed:.1f}s")
    print("   Top openers:")
    for word, h in all_scored[:15]:
        print(f"     {word}: {h:.4f} bits")

    best_opener = all_scored[0][0]
    print(f"   => Best opener: {best_opener!r} ({all_scored[0][1]:.4f} bits)", flush=True)

    # ── Step 2: Compute opener patterns → candidate groups ─────────────────────
    print(f"\n[2/3] Partitioning answer words by '{best_opener}' opening pattern …", flush=True)
    t0 = time.perf_counter()

    pattern_groups: dict[int, list[str]] = {}
    for secret in answer_words:
        p = _pattern_int(best_opener, secret)
        pattern_groups.setdefault(p, []).append(secret)

    n_patterns = len(pattern_groups)
    avg_candidates = sum(len(v) for v in pattern_groups.values()) / n_patterns
    elapsed = time.perf_counter() - t0
    print(f"   {n_patterns} distinct patterns, avg {avg_candidates:.1f} candidates each  ({elapsed:.2f}s)")

    # ── Step 3: For each pattern find best turn-2 word from full pool ──────────
    print("\n[3/3] Computing best turn-2 guess for each opening pattern …", flush=True)
    print(f"   (evaluating {len(guess_words)} × avg {avg_candidates:.0f} = "
          f"{len(guess_words) * avg_candidates:,.0f} patterns per group ×  {n_patterns} groups)")
    t0 = time.perf_counter()

    # Patterns where the puzzle is already solved by the opener (candidates = [secret])
    # — no need to compute; we'd just guess the remaining word.
    tasks = [
        (pat, cands, guess_words)
        for pat, cands in sorted(pattern_groups.items(), key=lambda x: -len(x[1]))
        if pat != ALL_GREEN  # opener solved it already
    ]

    lookup: dict[int, str] = {ALL_GREEN: best_opener}  # opener already solved

    total_tasks = len(tasks)
    completed = 0
    with ProcessPoolExecutor() as pool:
        for pat, best_word, best_h in pool.map(_compute_turn2_for_pattern, tasks, chunksize=1):
            lookup[pat] = best_word
            completed += 1
            elapsed_so_far = time.perf_counter() - t0
            if completed % 10 == 0 or completed == total_tasks:
                pct = completed / total_tasks * 100
                eta = (elapsed_so_far / completed) * (total_tasks - completed)
                print(f"   {completed}/{total_tasks} ({pct:.0f}%)  ETA {eta:.0f}s", flush=True)

    elapsed = time.perf_counter() - t0
    print(f"   Done in {elapsed:.1f}s", flush=True)

    # ── Print Python source code for hardcoding ────────────────────────────────
    print("\n" + "=" * 70)
    print("# Paste the following into src/wordle/solver/strategy.py")
    print("=" * 70)
    print(f'\nMODE_C_OPENER = "{best_opener}"')
    print()
    print("# Maps opener-pattern (int) → best turn-2 guess from full guess pool.")
    print("# Key = sum(score[i] * 3^i for i in range(5)), Value = guess word.")
    print("# Precomputed by scripts/precompute_mode_c.py (run once offline).")
    print("MODE_C_TURN2: dict[int, str] = {")
    for pat, word in sorted(lookup.items()):
        cands = pattern_groups.get(pat, [])
        print(f"    {pat}: {word!r},  # {len(cands)} candidates")
    print("}")

    # ── Sanity: quick estimate of avg turns with this strategy ─────────────────
    print("\n\n[Sanity] Quick avg-turns estimate on 300 random words …", flush=True)
    import random
    rng = random.Random(42)
    sample = rng.sample(answer_words, min(300, len(answer_words)))

    from wordle.solver.constraints import SolverConstraints
    from wordle.constants import MAX_TURNS

    total_turns = 0
    solved_count = 0
    for secret in sample:
        constraints = SolverConstraints()
        tried: set[str] = set()
        words_tried: list[str] = []

        for turn in range(MAX_TURNS):
            candidates = [w for w in answer_words if constraints.candidate_matches(w)]
            if not candidates:
                break

            if turn == 0:
                guess = best_opener
            elif len(candidates) == 1:
                guess = candidates[0]
            elif turn == 1:
                # Use precomputed lookup
                op_pat = _pattern_int(best_opener, secret)
                guess = lookup.get(op_pat, candidates[0])
                # If the lookup word was already tried (unlikely but safe), pick entropy
                if guess in tried:
                    guess = candidates[0]
            else:
                # Candidates-only entropy
                best_h = -1.0
                guess = candidates[0]
                cache: dict[tuple[str, str], int] = {}
                for w in candidates:
                    if w in tried:
                        continue
                    counts_inner: Counter[int] = Counter()
                    for sec2 in candidates:
                        k = (w, sec2)
                        if k not in cache:
                            cache[k] = _pattern_int(w, sec2)
                        counts_inner[cache[k]] += 1
                    h = _entropy(counts_inner)
                    if h > best_h:
                        best_h = h
                        guess = w

            tried.add(guess)
            words_tried.append(guess)
            sc = score_guess(secret, guess)
            if all(v == 2 for v in sc):
                total_turns += len(words_tried)
                solved_count += 1
                break
            constraints.update(guess, sc)

    avg = total_turns / solved_count if solved_count else 999.0
    print(f"   Sample avg turns: {avg:.4f}  ({solved_count}/{len(sample)} solved)")
    print("\nDone. Copy the MODE_C_OPENER and MODE_C_TURN2 dict into strategy.py.")


if __name__ == "__main__":
    main()
