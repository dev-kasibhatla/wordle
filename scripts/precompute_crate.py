#!/usr/bin/env python3
"""Precompute mode C lookup tables for the 'crate' opener.

This script computes:
  - MODE_C_TURN2: best turn-2 word per opener pattern (128 entries)
  - MODE_C_TURN3: best turn-3 word per (opener_pat, turn2_pat) pair

Uses full 12k guess pool for entropy selection.

Usage:
    uv run python scripts/precompute_crate.py > /tmp/crate_output.txt
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

OPENER = "crate"
ALL_GREEN = 242


def _pat(guess: str, secret: str) -> int:
    sc = score_guess(secret, guess)
    return sc[0] + 3 * sc[1] + 9 * sc[2] + 27 * sc[3] + 81 * sc[4]


def _best_entropy(candidates: list[str], pool: list[str]) -> str:
    cset = set(candidates)
    n = len(candidates)
    bw, bh = candidates[0], -1.0
    for w in pool:
        counts = Counter(_pat(w, s) for s in candidates)
        h = -sum((c / n) * log2(c / n) for c in counts.values())
        if w in cset:
            h += 0.5 / max(n, 1)
        if h > bh:
            bh = h
            bw = w
    return bw


def _worker_t2(args: tuple) -> tuple[int, str]:
    p1, group, pool = args
    if len(group) == 1:
        return p1, group[0]
    return p1, _best_entropy(group, pool)


def _worker_t3(args: tuple) -> tuple[int, int, str]:
    p1, p2, candidates, pool = args
    if not candidates:
        return p1, p2, ""
    if len(candidates) == 1:
        return p1, p2, candidates[0]
    return p1, p2, _best_entropy(candidates, pool)


def _estimate(answer_words, guess_words, t2, t3) -> None:
    from wordle.solver.constraints import SolverConstraints
    from wordle.constants import MAX_TURNS

    total, solved, hist, failed = 0, 0, {}, []
    for secret in answer_words:
        constraints = SolverConstraints()
        tried: set[str] = set()
        for turn in range(MAX_TURNS):
            candidates = [w for w in answer_words if constraints.candidate_matches(w)]
            if not candidates:
                break
            if turn == 0:
                guess = OPENER
            elif turn == 1:
                p1 = _pat(OPENER, secret)
                guess = t2.get(p1, candidates[0])
                if guess in tried:
                    guess = candidates[0]
            elif turn == 2:
                if len(candidates) == 1:
                    guess = candidates[0]
                else:
                    p1 = _pat(OPENER, secret)
                    t2w = t2.get(p1, "")
                    p2 = _pat(t2w, secret) if t2w else 0
                    guess = t3.get((p1, p2), "")
                    if not guess or guess in tried:
                        pool = guess_words if len(candidates) > 3 else candidates
                        guess = _best_entropy(candidates, pool)
            elif len(candidates) <= 2:
                guess = next((w for w in candidates if w not in tried), candidates[0])
            else:
                pool = guess_words if len(candidates) > 3 else candidates
                guess = _best_entropy(candidates, pool)
            tried.add(guess)
            sc = score_guess(secret, guess)
            if all(v == 2 for v in sc):
                total += turn + 1
                solved += 1
                hist[turn + 1] = hist.get(turn + 1, 0) + 1
                break
            constraints.update(guess, sc)
        else:
            failed.append(secret)
            total += 6
    avg = total / len(answer_words) if answer_words else 0.0
    print(f"  avg={avg:.4f}  solved={solved}/{len(answer_words)}  failed={len(failed)}")
    if failed:
        print(f"  failures: {failed[:10]}")
    print(f"  histogram: {hist}", flush=True)


def main() -> None:
    data = load_wordle_data()
    answer_words = list(data.official_answers)
    guess_words = list(data.guess_words)
    print(f"Opener: {OPENER!r}  Answers: {len(answer_words)}  Guesses: {len(guess_words)}", flush=True)

    # Build opener groups
    opener_groups: dict[int, list[str]] = defaultdict(list)
    for secret in answer_words:
        opener_groups[_pat(OPENER, secret)].append(secret)
    print(f"Opener creates {len(opener_groups)} groups, max={max(len(v) for v in opener_groups.values())}", flush=True)

    # --- T2 lookup ---
    print("\nComputing turn-2 lookup...", flush=True)
    t0 = time.perf_counter()
    tasks_t2 = [(p, grp, guess_words) for p, grp in sorted(opener_groups.items(), key=lambda x: -len(x[1]))]
    t2: dict[int, str] = {}
    with ProcessPoolExecutor() as ex:
        for p, w in ex.map(_worker_t2, tasks_t2, chunksize=10):
            t2[p] = w
    print(f"  Done: {len(t2)} entries in {time.perf_counter()-t0:.1f}s", flush=True)

    # --- T3 groups ---
    print("\nBuilding turn-3 groups...", flush=True)
    t3_groups: dict[tuple[int, int], list[str]] = defaultdict(list)
    for secret in answer_words:
        p1 = _pat(OPENER, secret)
        t2w = t2.get(p1, "")
        if not t2w:
            continue
        p2 = _pat(t2w, secret)
        if p2 == ALL_GREEN:
            continue
        t3_groups[(p1, p2)].append(secret)
    groups_need_t3 = {k: v for k, v in t3_groups.items() if len(v) > 1}
    max_g = max(len(v) for v in groups_need_t3.values()) if groups_need_t3 else 0
    print(f"  {len(groups_need_t3)} groups, max={max_g}", flush=True)

    # --- T3 lookup ---
    print("\nComputing turn-3 lookup...", flush=True)
    t0 = time.perf_counter()
    tasks_t3 = [
        (p1, p2, cands, guess_words if len(cands) > 3 else cands)
        for (p1, p2), cands in sorted(groups_need_t3.items(), key=lambda x: -len(x[1]))
    ]
    t3: dict[tuple[int, int], str] = {}
    with ProcessPoolExecutor() as ex:
        for p1, p2, w in ex.map(_worker_t3, tasks_t3, chunksize=20):
            t3[(p1, p2)] = w
    print(f"  Done: {len(t3)} entries in {time.perf_counter()-t0:.1f}s", flush=True)

    # --- Estimate ---
    print("\nEstimating avg turns...", flush=True)
    _estimate(answer_words, guess_words, t2, t3)

    # --- Print dicts ---
    print("\n" + "=" * 70)
    print(f'MODE_C_OPENER = "{OPENER}"')
    print()
    print("MODE_C_TURN2: dict[int, str] = {")
    for k, v in sorted(t2.items()):
        print(f"    {k}: {v!r},")
    print("}")
    print()
    print("MODE_C_TURN3: dict[tuple[int, int], str] = {")
    for k, v in sorted(t3.items()):
        print(f"    {k}: {v!r},")
    print("}")


if __name__ == "__main__":
    main()
