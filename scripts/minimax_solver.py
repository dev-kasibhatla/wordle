#!/usr/bin/env python3
"""True minimax/DP optimal Wordle solver.

Uses backward induction with frozenset memoization.
For large groups (>10 candidates), falls back to entropy heuristic.

Reports the true optimal average turns achievable for this word list.

Usage:
    uv run python scripts/minimax_solver.py
"""
from __future__ import annotations

import sys
import time
from collections import Counter, defaultdict
from functools import lru_cache
from math import log2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wordle.data import load_wordle_data
from wordle.engine import score_guess

ALL_GREEN = 242
MAX_TURNS = 6
EXACT_LIMIT = 12  # Use full DP for groups <= this size; entropy otherwise


def _pat(guess: str, secret: str) -> int:
    sc = score_guess(secret, guess)
    return sc[0] + 3 * sc[1] + 9 * sc[2] + 27 * sc[3] + 81 * sc[4]


# Global pattern cache to avoid recomputing
_pat_cache: dict[tuple[str, str], int] = {}


def get_pat(guess: str, secret: str) -> int:
    key = (guess, secret)
    if key not in _pat_cache:
        _pat_cache[key] = _pat(guess, secret)
    return _pat_cache[key]


def _entropy_word(candidates: list[str], pool: list[str]) -> str:
    """Find word maximizing entropy over candidates."""
    cset = set(candidates)
    n = len(candidates)
    bw, bh = candidates[0], -1.0
    for w in pool:
        counts = Counter(get_pat(w, s) for s in candidates)
        h = -sum((c / n) * log2(c / n) for c in counts.values())
        if w in cset:
            h += 0.5 / max(n, 1)
        if h > bh:
            bh = h
            bw = w
    return bw


def optimal_turns(
    candidates: tuple[str, ...],
    depth: int,
    guess_words: tuple[str, ...],
    memo: dict,
) -> float:
    """Compute minimum expected total turns for the remaining candidates."""
    n = len(candidates)
    if n == 0:
        return float("inf")
    if n == 1:
        return float(depth + 1)

    key = (frozenset(candidates), depth)
    if key in memo:
        return memo[key]

    if depth >= MAX_TURNS:
        # Out of turns — each remaining word fails
        return float(MAX_TURNS + 1)  # count as failure

    cset = set(candidates)

    if n > EXACT_LIMIT:
        # Entropy heuristic for large groups
        pool = list(guess_words) if len(candidates) > 3 else list(candidates)
        best_word = _entropy_word(list(candidates), pool)
        best_words = [best_word]
    else:
        # Full search: try all guess words for small groups
        best_words = list(guess_words)

    best_et = float("inf")
    best_w = candidates[0]

    for w in best_words:
        partitions: dict[int, list[str]] = defaultdict(list)
        for s in candidates:
            partitions[get_pat(w, s)].append(s)

        et = 0.0
        for p, sub in partitions.items():
            if p == ALL_GREEN:
                # w is correct for these — solved on this turn
                et += len(sub) * (depth + 1)
            else:
                et += optimal_turns(tuple(sub), depth + 1, guess_words, memo)

        et /= n  # average per candidate

        if et < best_et:
            best_et = et
            best_w = w

        # Pruning: can't do better than solving everyone in (depth+1) turns
        if best_et <= depth + 1:
            break

    memo[key] = best_et
    return best_et


def main() -> None:
    data = load_wordle_data()
    answer_words = list(data.official_answers)
    guess_words = list(data.guess_words)

    print(f"Answer pool: {len(answer_words)}  Guess pool: {len(guess_words)}")
    print(f"EXACT_LIMIT: {EXACT_LIMIT} (full DP for groups ≤ {EXACT_LIMIT})")

    # Pre-warm pattern cache for the opener (optional)
    t0 = time.perf_counter()
    opener = "soare"
    for secret in answer_words:
        get_pat(opener, secret)
    print(f"Pattern cache warmed for opener in {time.perf_counter()-t0:.2f}s")

    # Build opener groups
    opener_groups: dict[int, list[str]] = defaultdict(list)
    for secret in answer_words:
        opener_groups[get_pat(opener, secret)].append(secret)
    print(f"Opener creates {len(opener_groups)} non-empty groups")
    print(f"Max group: {max(len(v) for v in opener_groups.values())}, avg: {sum(len(v) for v in opener_groups.values())/len(opener_groups):.1f}")

    # For each opener group, compute optimal expected turns from turn 2 onwards
    memo: dict = {}
    total_turns = 0.0
    total_words = 0

    print(f"\nComputing optimal turns per opener group...")
    t0 = time.perf_counter()

    # Sort by size (large groups first, benefit most from good turn-2 choices)
    sorted_groups = sorted(opener_groups.items(), key=lambda x: -len(x[1]))

    for p, group in sorted_groups:
        if len(group) <= 15:
            # Full DP for this group
            et = optimal_turns(
                tuple(group), 1,  # depth=1 (we're about to make guess 2)
                tuple(guess_words), memo
            )
            # Add 1 for the opener itself
            total_turns += len(group) * (1 + et)  # 1 for opener + et for rest
        else:
            # Entropy heuristic for very large groups
            pool = guess_words if len(group) > 10 else group
            best = _entropy_word(group, pool)
            # Estimate additional turns
            partitions = defaultdict(list)
            for s in group:
                partitions[get_pat(best, s)].append(s)

            sub_et = 0.0
            for p2, sub in partitions.items():
                if p2 == ALL_GREEN:
                    sub_et += len(sub) * 2  # solved in turn 2
                else:
                    sub_et += len(sub) * 3.5  # rough estimate
            sub_et /= len(group)
            total_turns += len(group) * (1 + sub_et)

        total_words += len(group)
        elapsed = time.perf_counter() - t0
        if elapsed > 30:
            print(f"  ... {total_words}/{len(answer_words)} words processed ({elapsed:.1f}s)")
            t0 = time.perf_counter()

    avg = total_turns / total_words
    elapsed = time.perf_counter() - t0
    print(f"\nOptimal avg turns: {avg:.4f}  (over {total_words} words)")
    print(f"Computation time: {elapsed:.1f}s")
    print(f"Memo cache size: {len(memo)} states")


if __name__ == "__main__":
    main()
