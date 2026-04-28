#!/usr/bin/env python3
"""Precompute mode C turn-3 lookup table.

After soare + turn-2, groups are typically 1-5 candidates.
We precompute the best turn-3 guess for each (opener_pat, turn2_pat) combination.

Usage:
    uv run python scripts/precompute_mode_c_t3.py
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
from wordle.solver.strategy import MODE_C_OPENER, MODE_C_TURN2


def _pat(guess: str, secret: str) -> int:
    sc = score_guess(secret, guess)
    return sc[0] + 3*sc[1] + 9*sc[2] + 27*sc[3] + 81*sc[4]


ALL_GREEN = 242


def _entropy(counts: Counter) -> float:
    n = sum(counts.values())
    if n <= 1:
        return 0.0
    h = 0.0
    for c in counts.values():
        p = c / n
        h -= p * log2(p)
    return h


def _best_word(candidates: list[str], pool: list[str]) -> str:
    cset = set(candidates)
    best_w, best_h = "", -1.0
    n = len(candidates)
    for w in pool:
        counts: Counter[int] = Counter(_pat(w, s) for s in candidates)
        h = _entropy(counts)
        if w in cset:
            h += 0.5 / max(n, 1)
        if h > best_h:
            best_h = h
            best_w = w
    return best_w


def _worker(args: tuple) -> tuple[int, int, str]:
    key_p1, key_p2, candidates, pool = args
    if not candidates:
        return key_p1, key_p2, ""
    if len(candidates) == 1:
        return key_p1, key_p2, candidates[0]
    return key_p1, key_p2, _best_word(candidates, pool)


def main() -> None:
    data = load_wordle_data()
    answer_words = list(data.official_answers)
    guess_words = list(data.guess_words)

    print(f"Answer pool: {len(answer_words)}  Guess pool: {len(guess_words)}")

    # Build (opener_pat, turn2_pat) -> [remaining candidates]
    print("\nPartitioning by (opener_pat, turn2_pat)...")
    t0 = time.perf_counter()
    groups: dict[tuple[int, int], list[str]] = {}
    for secret in answer_words:
        p1 = _pat(MODE_C_OPENER, secret)
        t2_word = MODE_C_TURN2.get(p1, "")
        if not t2_word or t2_word == secret:
            continue  # already solved or no lookup
        p2 = _pat(t2_word, secret)
        key = (p1, p2)
        groups.setdefault(key, []).append(secret)

    # Remove groups where puzzle was already solved (p2 == ALL_GREEN)
    groups = {k: v for k, v in groups.items() if k[1] != ALL_GREEN and len(v) > 1}
    elapsed = time.perf_counter() - t0
    n_groups = len(groups)
    max_g = max(len(v) for v in groups.values())
    avg_g = sum(len(v) for v in groups.values()) / max(n_groups, 1)
    print(f"  {n_groups} groups needing turn-3, max={max_g}, avg={avg_g:.1f}  ({elapsed:.2f}s)")

    # For efficiency: use full guess pool only when group size > 3
    tasks = []
    for (p1, p2), cands in sorted(groups.items(), key=lambda x: -len(x[1])):
        pool = guess_words if len(cands) > 3 else cands
        tasks.append((p1, p2, cands, pool))

    print(f"\nComputing best turn-3 for {len(tasks)} groups...")
    t0 = time.perf_counter()
    lookup: dict[tuple[int, int], str] = {}
    with ProcessPoolExecutor() as pool_exec:
        for p1, p2, best_w in pool_exec.map(_worker, tasks, chunksize=20):
            lookup[(p1, p2)] = best_w

    elapsed = time.perf_counter() - t0
    print(f"  Done in {elapsed:.1f}s")

    # Estimate avg turns with turn-3 lookup
    print("\nEstimating avg turns with turn-3 lookup...")
    from wordle.solver.constraints import SolverConstraints
    from wordle.constants import MAX_TURNS

    total_t = 0
    solved_c = 0
    failed_words = []
    for secret in answer_words:
        constraints = SolverConstraints()
        tried: set[str] = set()
        words_tried: list[str] = []

        for turn in range(MAX_TURNS):
            candidates = [w for w in answer_words if constraints.candidate_matches(w)]
            if not candidates:
                break

            if turn == 0:
                guess = MODE_C_OPENER
            elif turn == 1:
                p1 = _pat(MODE_C_OPENER, secret)
                guess = MODE_C_TURN2.get(p1, candidates[0])
                if guess in tried:
                    guess = candidates[0]
            elif turn == 2:
                # Use turn-3 lookup
                if len(candidates) == 1:
                    guess = candidates[0]
                else:
                    prev1 = _pat(MODE_C_OPENER, secret)
                    t2w = MODE_C_TURN2.get(prev1, "")
                    prev2 = _pat(t2w, secret) if t2w else 0
                    guess = lookup.get((prev1, prev2), "")
                    if not guess or guess in tried:
                        # fallback: candidates entropy
                        pool_use = guess_words if len(candidates) > 3 else candidates
                        guess = ""
                        best_h = -1.0
                        cset = set(candidates)
                        for w in pool_use:
                            if w in tried:
                                continue
                            counts: Counter[int] = Counter(_pat(w, s) for s in candidates)
                            h = _entropy(counts)
                            if w in cset:
                                h += 0.5/max(len(candidates),1)
                            if h > best_h:
                                best_h = h
                                guess = w
            else:
                # Turn 4+: candidates-only entropy
                pool_use = guess_words if len(candidates) > 3 else candidates
                guess = ""
                best_h = -1.0
                cset = set(candidates)
                for w in pool_use:
                    if w in tried:
                        continue
                    counts = Counter(_pat(w, s) for s in candidates)
                    h = _entropy(counts)
                    if w in cset:
                        h += 0.5/max(len(candidates),1)
                    if h > best_h:
                        best_h = h
                        guess = w
                if not guess:
                    guess = candidates[0]

            tried.add(guess)
            words_tried.append(guess)
            sc = score_guess(secret, guess)
            if all(v == 2 for v in sc):
                total_t += len(words_tried)
                solved_c += 1
                break
            constraints.update(guess, sc)
        else:
            failed_words.append(secret)

    avg = total_t / solved_c if solved_c else 999.0
    print(f"  avg={avg:.4f}  solved={solved_c}/{len(answer_words)}  failed={len(failed_words)}")
    if failed_words:
        print(f"  failures: {failed_words[:10]}")

    # Print Python source
    print("\n" + "="*70)
    print("MODE_C_TURN3: dict[tuple[int, int], str] = {")
    for (p1, p2), word in sorted(lookup.items()):
        print(f"    ({p1}, {p2}): {word!r},")
    print("}")
    print("="*70)


if __name__ == "__main__":
    main()
