#!/usr/bin/env python3
"""Optimize mode C by recomputing turn-2 and turn-3 lookups using min-expected-turns objective.

This replaces the pure entropy objective with a properly calibrated ET objective
that accounts for the fact that:
- Guessing a candidate is better than a discriminator for small groups (size 2-4)
- For size-2: E = 3.5 turns (optimal, irreducible)
- For size-3: E = 3.67 turns (optimal with candidate guess)
- For larger groups: E depends on the turn-3 guess quality

Usage:
    uv run python scripts/optimize_mode_c.py
"""
from __future__ import annotations

import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from math import log2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wordle.data import load_wordle_data
from wordle.engine import score_guess
from wordle.solver.strategy import MODE_C_OPENER


def _pat(guess: str, secret: str) -> int:
    sc = score_guess(secret, guess)
    return sc[0] + 3 * sc[1] + 9 * sc[2] + 27 * sc[3] + 81 * sc[4]


ALL_GREEN = 242


def _et_for_size(n: int) -> float:
    """Expected total turns (from turn 3 = 3rd guess) given n candidates remain.
    Uses optimal strategy: for small n, guess candidates; for large n, entropy.
    """
    if n <= 0:
        return 0.0
    if n == 1:
        return 3.0   # solved in turn 3 directly
    if n == 2:
        return 3.5   # optimal: 1/2 in 3, 1/2 in 4
    if n == 3:
        return 3.67  # optimal: 1/3 in 3, 2/3 in 4 (guess candidate)
    if n == 4:
        return 3.75  # 1/4 in 3, 3/4 in 4 (if perfect-split candidate exists)
    if n <= 6:
        return 4.0   # need turn 4 for most
    if n <= 12:
        return 4.33  # need turn 4-5
    if n <= 24:
        return 4.67
    return 5.0


def _best_min_et_word_turn2(group: list[str], pool: list[str]) -> str:
    """Find the word from pool that minimizes expected total turns for the group."""
    n = len(group)
    if n == 0:
        return pool[0] if pool else ""
    if n == 1:
        return group[0]

    group_set = set(group)
    best_w, best_score = "", float("inf")

    for w in pool:
        partitions = defaultdict(int)
        for s in group:
            partitions[_pat(w, s)] += 1

        # Compute expected total turns for this word
        total = 0.0
        for p, cnt in partitions.items():
            if p == ALL_GREEN:
                total += cnt * 3.0  # solved immediately on turn 3
            else:
                total += cnt * _et_for_size(cnt)

        score = total / n  # avg turns per word in group

        # Prefer candidates (if candidate guessed correctly, saves 1 turn)
        if w in group_set:
            # Being a candidate means 1/n chance of solving in 3 turns
            # This is already captured in et_for_size but we add a small tie-breaker
            score -= 0.01

        if score < best_score:
            best_score = score
            best_w = w

    return best_w


def _worker_turn2(args: tuple) -> tuple[int, str]:
    opener_pat, group, pool = args
    return opener_pat, _best_min_et_word_turn2(group, pool)


def _best_min_et_word_turn3(candidates: list[str], pool: list[str]) -> str:
    """Find the word from pool that minimizes expected total turns (turn 4+) for candidates."""
    n = len(candidates)
    if n <= 0:
        return candidates[0] if candidates else ""
    if n == 1:
        return candidates[0]

    candidate_set = set(candidates)
    best_w, best_score = candidates[0], float("inf")

    for w in pool:
        partitions = defaultdict(int)
        for s in candidates:
            partitions[_pat(w, s)] += 1

        # Expected additional turns (after this guess = turn 4 total)
        total = 0.0
        for p, cnt in partitions.items():
            if p == ALL_GREEN:
                total += cnt * 4.0  # solved on turn 4
            elif cnt == 1:
                total += cnt * 5.0  # 1 more guess needed → turn 5
            elif cnt == 2:
                total += cnt * 5.5  # avg 5.5 turns
            elif cnt == 3:
                total += cnt * 5.67
            else:
                total += cnt * (5.0 + log2(cnt))

        score = total / n

        if w in candidate_set:
            score -= 0.01  # tie-breaker for candidates

        if score < best_score:
            best_score = score
            best_w = w

    return best_w


def _worker_turn3(args: tuple) -> tuple[int, int, str]:
    p1, p2, candidates, pool = args
    return p1, p2, _best_min_et_word_turn3(candidates, pool)


def _estimate_avg(
    answer_words: list[str],
    guess_words: list[str],
    turn2_lookup: dict[int, str],
    turn3_lookup: dict[tuple[int, int], str],
) -> float:
    from wordle.solver.constraints import SolverConstraints
    from wordle.constants import MAX_TURNS

    total = 0
    solved = 0
    failed = []

    for secret in answer_words:
        constraints = SolverConstraints()
        tried: set[str] = set()

        for turn in range(MAX_TURNS):
            candidates = [w for w in answer_words if constraints.candidate_matches(w)]
            if not candidates:
                break

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
                        pool = guess_words if len(candidates) > 3 else candidates
                        guess = _best_min_et_word_turn3(candidates, pool) if pool is not candidates else candidates[0]
                        if not guess or guess in tried:
                            guess = next((w for w in candidates if w not in tried), candidates[0])
            else:
                pool = guess_words if len(candidates) > 3 else candidates
                # Simple greedy: pick best candidate
                guess = next((w for w in candidates if w not in tried), candidates[0])

            tried.add(guess)
            sc = score_guess(secret, guess)
            if all(v == 2 for v in sc):
                total += turn + 1
                solved += 1
                break
            constraints.update(guess, sc)
        else:
            failed.append(secret)
            total += 6

    avg = total / len(answer_words) if answer_words else 0.0
    print(f"  avg={avg:.4f}  solved={solved}/{len(answer_words)}  failed={len(failed)}")
    if failed:
        print(f"  failures: {failed[:10]}")
    return avg


def main() -> None:
    data = load_wordle_data()
    answer_words = list(data.official_answers)
    guess_words = list(data.guess_words)

    print(f"Answer pool: {len(answer_words)}  Guess pool: {len(guess_words)}")

    # Step 1: Build opener groups
    print("\nBuilding opener groups...")
    opener_groups: dict[int, list[str]] = defaultdict(list)
    for secret in answer_words:
        p = _pat(MODE_C_OPENER, secret)
        opener_groups[p].append(secret)
    print(f"  {len(opener_groups)} opener patterns, max={max(len(v) for v in opener_groups.values())}")

    # Step 2: Compute best turn-2 word per opener pattern using min-ET
    print("\nComputing optimized turn-2 lookup (min-ET objective)...")
    t0 = time.perf_counter()
    tasks = [
        (p, group, guess_words)
        for p, group in sorted(opener_groups.items(), key=lambda x: -len(x[1]))
    ]
    turn2_lookup: dict[int, str] = {}
    with ProcessPoolExecutor() as executor:
        for p, w in executor.map(_worker_turn2, tasks, chunksize=10):
            turn2_lookup[p] = w
    elapsed = time.perf_counter() - t0
    print(f"  Done in {elapsed:.1f}s  ({len(turn2_lookup)} entries)")

    # Step 3: Build groups after turn 2 for turn-3 computation
    print("\nBuilding turn-3 groups...")
    t0 = time.perf_counter()
    turn3_groups: dict[tuple[int, int], list[str]] = defaultdict(list)
    for secret in answer_words:
        p1 = _pat(MODE_C_OPENER, secret)
        t2w = turn2_lookup.get(p1, "")
        if not t2w:
            continue
        p2 = _pat(t2w, secret)
        if p2 == ALL_GREEN:
            continue  # already solved in 2 turns
        key = (p1, p2)
        turn3_groups[key].append(secret)

    # Only need turn-3 for groups > 1
    groups_needing_t3 = {k: v for k, v in turn3_groups.items() if len(v) > 1}
    elapsed = time.perf_counter() - t0
    max_g = max(len(v) for v in groups_needing_t3.values()) if groups_needing_t3 else 0
    avg_g = (
        sum(len(v) for v in groups_needing_t3.values()) / len(groups_needing_t3)
        if groups_needing_t3
        else 0
    )
    print(f"  {len(groups_needing_t3)} groups needing turn-3, max={max_g}, avg={avg_g:.1f}  ({elapsed:.2f}s)")

    # Step 4: Compute best turn-3 word per group using min-ET
    print(f"\nComputing optimized turn-3 lookup (min-ET objective)...")
    t0 = time.perf_counter()
    tasks3 = [
        (p1, p2, cands, guess_words if len(cands) > 3 else cands)
        for (p1, p2), cands in sorted(groups_needing_t3.items(), key=lambda x: -len(x[1]))
    ]
    turn3_lookup: dict[tuple[int, int], str] = {}
    with ProcessPoolExecutor() as executor:
        for p1, p2, w in executor.map(_worker_turn3, tasks3, chunksize=20):
            turn3_lookup[(p1, p2)] = w
    elapsed = time.perf_counter() - t0
    print(f"  Done in {elapsed:.1f}s  ({len(turn3_lookup)} entries)")

    # Step 5: Estimate avg turns
    print("\nEstimating avg turns with optimized lookups...")
    _estimate_avg(answer_words, guess_words, turn2_lookup, turn3_lookup)

    # Print Python source for integration
    print("\n" + "=" * 70)
    print("# MODE_C_TURN2 (min-ET optimized):")
    print("MODE_C_TURN2_OPT: dict[int, str] = {")
    for k, v in sorted(turn2_lookup.items()):
        print(f"    {k}: {v!r},")
    print("}")

    print("\n# MODE_C_TURN3 (min-ET optimized):")
    print("MODE_C_TURN3_OPT: dict[tuple[int, int], str] = {")
    for k, v in sorted(turn3_lookup.items()):
        print(f"    {k}: {v!r},")
    print("}")


if __name__ == "__main__":
    main()
