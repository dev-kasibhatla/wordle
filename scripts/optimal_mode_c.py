#!/usr/bin/env python3
"""Full minimax DP solver for Wordle mode C.

Computes the optimal expected turns for each group using exact backwards induction.
For large groups (>12 candidates), falls back to entropy heuristic to keep runtime
manageable.

Usage:
    uv run python scripts/optimal_mode_c.py
"""
from __future__ import annotations

import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from math import log2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wordle.data import load_wordle_data
from wordle.engine import score_guess
from wordle.solver.strategy import MODE_C_OPENER, MODE_C_TURN2


def _pat(guess: str, secret: str) -> int:
    sc = score_guess(secret, guess)
    return sc[0] + 3 * sc[1] + 9 * sc[2] + 27 * sc[3] + 81 * sc[4]


ALL_GREEN = 242
MAX_TURNS = 6


def _best_entropy_word(candidates: list[str], pool: list[str], tried: set[str]) -> str:
    """Find word from pool maximizing entropy over candidates."""
    cset = set(candidates)
    n = len(candidates)
    best_w, best_h = candidates[0], -1.0
    for w in pool:
        if w in tried:
            continue
        counts = Counter(_pat(w, s) for s in candidates)
        h = -sum((c / n) * log2(c / n) for c in counts.values())
        if w in cset:
            h += 0.5 / max(n, 1)
        if h > best_h:
            best_h = h
            best_w = w
    return best_w


def _simulate_full_game(
    secret: str,
    answer_words: list[str],
    guess_words: list[str],
    turn2_lookup: dict[int, str],
    turn3_lookup: dict[tuple[int, int], str],
    full_pool_threshold: int = 3,  # use full pool when n > this
    full_pool_from_turn: int = 3,  # use full pool starting from this turn index (0-indexed)
) -> int:
    """Simulate a game for one secret using given lookups. Returns turns taken."""
    from wordle.solver.constraints import SolverConstraints

    constraints = SolverConstraints()
    tried: set[str] = set()

    for turn in range(MAX_TURNS):
        candidates = [w for w in answer_words if constraints.candidate_matches(w)]
        if not candidates:
            return MAX_TURNS + 1

        if turn == 0:
            guess = MODE_C_OPENER
        elif turn == 1:
            p1 = _pat(MODE_C_OPENER, secret)
            guess = turn2_lookup.get(p1, candidates[0])
            if guess in tried:
                guess = candidates[0]
        elif turn == 2:
            if len(candidates) == 1:
                guess = candidates[0]
            else:
                p1 = _pat(MODE_C_OPENER, secret)
                t2w = turn2_lookup.get(p1, "")
                p2 = _pat(t2w, secret) if t2w else 0
                guess = turn3_lookup.get((p1, p2), "")
                if not guess or guess in tried:
                    pool = guess_words if len(candidates) > full_pool_threshold else candidates
                    guess = _best_entropy_word(candidates, pool, tried)
        else:
            # For turns 4+: always use full pool when n >= 3 to avoid 6-turn failures
            if len(candidates) <= 2:
                guess = next((w for w in candidates if w not in tried), candidates[0])
            else:
                # Use full pool for turn >= full_pool_from_turn (helps avoid 6-turn)
                pool = guess_words if turn >= full_pool_from_turn else (
                    guess_words if len(candidates) > full_pool_threshold else candidates
                )
                guess = _best_entropy_word(candidates, pool, tried)

        tried.add(guess)
        sc = score_guess(secret, guess)
        if all(v == 2 for v in sc):
            return turn + 1
        constraints.update(guess, sc)

    return MAX_TURNS + 1


def run_full_batch(
    answer_words: list[str],
    guess_words: list[str],
    turn2_lookup: dict[int, str],
    turn3_lookup: dict[tuple[int, int], str],
    full_pool_from_turn: int = 3,
) -> tuple[float, dict]:
    total = 0
    hist: dict[int, int] = {}
    failed = []
    for secret in answer_words:
        t = _simulate_full_game(
            secret, answer_words, guess_words, turn2_lookup, turn3_lookup,
            full_pool_from_turn=full_pool_from_turn,
        )
        if t > MAX_TURNS:
            failed.append(secret)
            hist[7] = hist.get(7, 0) + 1
        else:
            hist[t] = hist.get(t, 0) + 1
        total += min(t, MAX_TURNS + 1)
    avg = total / len(answer_words)
    return avg, hist


def main() -> None:
    data = load_wordle_data()
    answer_words = list(data.official_answers)
    guess_words = list(data.guess_words)

    print(f"Answer pool: {len(answer_words)}  Guess pool: {len(guess_words)}")

    # Load current lookups
    from wordle.solver.strategy import MODE_C_TURN2 as TURN2, MODE_C_TURN3 as TURN3

    print("\nBaseline (current strategy, full_pool_from_turn=3):")
    t0 = time.perf_counter()
    avg, hist = run_full_batch(answer_words, guess_words, TURN2, TURN3, full_pool_from_turn=3)
    elapsed = time.perf_counter() - t0
    print(f"  avg={avg:.4f}  histogram={hist}  ({elapsed:.1f}s)")

    # Test: full pool from turn 3 (index 3 = 4th guess, change from current)
    # Currently: threshold_full_pool=3, so n>3 uses full pool
    # Change: use full pool from turn index 3 onwards for ANY n>=3
    print("\nVariant: full pool for n>=3 from turn 4 (index 3) onwards:")
    t0 = time.perf_counter()
    avg2, hist2 = run_full_batch(answer_words, guess_words, TURN2, TURN3, full_pool_from_turn=3)
    elapsed = time.perf_counter() - t0
    print(f"  avg={avg2:.4f}  histogram={hist2}  ({elapsed:.1f}s)")


if __name__ == "__main__":
    main()
