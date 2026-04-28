#!/usr/bin/env python3
"""Exploration script for mode C strategy optimisation.

Runs multiple experiments to find the best opener, optimal thresholds,
and whether using the full guess pool improves avg turns vs answer pool.

Usage:
    uv run python scripts/mode_c_explore.py
"""
from __future__ import annotations

import sys
import random
import time
from collections import Counter
from math import log2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wordle.data import load_wordle_data
from wordle.engine import score_guess
from wordle.solver.constraints import SolverConstraints
from wordle.constants import MAX_TURNS

# ── Pattern encoding ──────────────────────────────────────────────────────────

_PATTERN_CACHE: dict[tuple[str, str], int] = {}


def _pattern_int(guess: str, secret: str) -> int:
    """Encode score_guess result as integer 0-242. Cached."""
    key = (guess, secret)
    cached = _PATTERN_CACHE.get(key)
    if cached is not None:
        return cached
    sc = score_guess(secret, guess)
    result = sc[0] + 3 * sc[1] + 9 * sc[2] + 27 * sc[3] + 81 * sc[4]
    _PATTERN_CACHE[key] = result
    return result


def _entropy_of_guess(guess: str, candidates: list[str]) -> float:
    """Expected bits of info from guessing `guess` when `candidates` remain."""
    n = len(candidates)
    if n <= 1:
        return 0.0
    counts: Counter[int] = Counter()
    for secret in candidates:
        counts[_pattern_int(guess, secret)] += 1
    h = 0.0
    for c in counts.values():
        p = c / n
        h -= p * log2(p)
    return h


# ── Opener benchmarking ───────────────────────────────────────────────────────

def rank_openers(candidates: list[str], pool: list[str], top_n: int = 20) -> list[tuple[str, float]]:
    """Rank words in pool by entropy against candidates. Returns (word, entropy) pairs."""
    results = []
    for word in pool:
        h = _entropy_of_guess(word, candidates)
        results.append((word, h))
    results.sort(key=lambda x: -x[1])
    return results[:top_n]


# ── Solver implementations ────────────────────────────────────────────────────

def _best_entropy_from_pool(
    pool: list[str], candidates: list[str], tried: set[str]
) -> str:
    """Select the guess from pool with highest entropy against candidates."""
    best_word = ""
    best_h = -1.0
    for word in pool:
        if word in tried:
            continue
        h = _entropy_of_guess(word, candidates)
        if h > best_h:
            best_h = h
            best_word = word
    if best_word:
        return best_word
    # fallback
    for word in candidates:
        if word not in tried:
            return word
    raise RuntimeError("no guess available")


def solve_mode_c(
    secret: str,
    answer_words: list[str],
    guess_words: list[str],
    opener: str,
    threshold_direct: int = 4,
    entropy_pool: str = "answer",  # "answer" or "full"
) -> tuple[int, bool]:
    """Solve one puzzle with the mode C strategy. Returns (turns, solved)."""
    constraints = SolverConstraints()
    tried: set[str] = set()
    words_tried: list[str] = []

    pool = answer_words if entropy_pool == "answer" else guess_words

    for turn in range(MAX_TURNS):
        candidates = [w for w in answer_words if constraints.candidate_matches(w)]
        if not candidates:
            break

        if turn == 0:
            guess = opener
        elif len(candidates) <= threshold_direct:
            # Direct: pick first untried candidate
            guess = next((w for w in candidates if w not in tried), None)
            if guess is None:
                break
        else:
            guess = _best_entropy_from_pool(pool, candidates, tried)

        tried.add(guess)
        words_tried.append(guess)
        sc = score_guess(secret, guess)
        if all(v == 2 for v in sc):
            return len(words_tried), True
        constraints.update(guess, sc)

    return len(words_tried), False


def benchmark(
    secrets: list[str],
    answer_words: list[str],
    guess_words: list[str],
    opener: str,
    threshold_direct: int = 4,
    entropy_pool: str = "answer",
) -> dict:
    """Run the strategy on all secrets, return summary statistics."""
    total_turns = 0
    solved_count = 0
    failed = []

    for secret in secrets:
        turns, solved = solve_mode_c(
            secret, answer_words, guess_words, opener,
            threshold_direct=threshold_direct, entropy_pool=entropy_pool,
        )
        total_turns += turns
        if solved:
            solved_count += 1
        else:
            failed.append(secret)

    n = len(secrets)
    avg = total_turns / solved_count if solved_count else 999.0
    return {
        "n": n,
        "solved": solved_count,
        "failed": len(failed),
        "solve_rate": solved_count / n,
        "avg_turns": avg,
        "failures": failed[:10],
    }


# ── Main experiments ──────────────────────────────────────────────────────────

def main() -> None:
    data = load_wordle_data()
    answer_words = list(data.official_answers)
    guess_words = list(data.guess_words)

    print(f"Answer pool: {len(answer_words)}  Guess pool: {len(guess_words)}")

    # ── Experiment 1: Find best opener from answer pool ───────────────────────
    print("\n=== EXPERIMENT 1: Best openers by entropy (answer pool) ===")
    t0 = time.perf_counter()
    top_openers_answers = rank_openers(answer_words, answer_words, top_n=15)
    elapsed = time.perf_counter() - t0
    print(f"Scored {len(answer_words)} answer-pool openers in {elapsed:.1f}s")
    for word, h in top_openers_answers:
        print(f"  {word}: {h:.4f} bits")

    # ── Experiment 2: Check known good openers from the full guess pool ───────
    print("\n=== EXPERIMENT 2: Known openers from full pool ===")
    known = ["crane", "raise", "slate", "trace", "soare", "arose", "stare",
             "snare", "irate", "audio", "rates", "tears", "reais", "arles",
             "crate", "tares", "later", "alter", "rales", "lares"]
    # keep only those in guess pool
    known = [w for w in known if w in set(guess_words)]
    t0 = time.perf_counter()
    known_scores = [(w, _entropy_of_guess(w, answer_words)) for w in known]
    known_scores.sort(key=lambda x: -x[1])
    elapsed = time.perf_counter() - t0
    print(f"Scored {len(known)} known openers in {elapsed:.2f}s")
    for word, h in known_scores:
        print(f"  {word}: {h:.4f} bits")

    # Best opener so far
    all_scored = known_scores + top_openers_answers
    all_scored.sort(key=lambda x: -x[1])
    best_opener = all_scored[0][0]
    print(f"\nBest opener so far: {best_opener} ({all_scored[0][1]:.4f} bits)")

    # ── Experiment 3: Benchmark on full answer set with best opener ───────────
    print("\n=== EXPERIMENT 3: Full benchmark — top openers, answer-pool entropy ===")
    top_to_test = [w for w, _ in all_scored[:5]]
    for opener in top_to_test:
        t0 = time.perf_counter()
        stats = benchmark(answer_words, answer_words, guess_words, opener,
                          threshold_direct=4, entropy_pool="answer")
        elapsed = time.perf_counter() - t0
        print(f"  opener={opener:8s}  avg={stats['avg_turns']:.4f}  "
              f"solve={stats['solve_rate']:.3%}  failed={stats['failed']}  "
              f"time={elapsed:.1f}s")

    # ── Experiment 4: Tune threshold_direct with best opener ─────────────────
    print("\n=== EXPERIMENT 4: Tune threshold_direct ===")
    for thresh in [2, 3, 4, 5, 6, 8]:
        t0 = time.perf_counter()
        stats = benchmark(answer_words, answer_words, guess_words, best_opener,
                          threshold_direct=thresh, entropy_pool="answer")
        elapsed = time.perf_counter() - t0
        print(f"  threshold={thresh}  avg={stats['avg_turns']:.4f}  "
              f"solve={stats['solve_rate']:.3%}  failed={stats['failed']}  "
              f"time={elapsed:.1f}s")

    # ── Experiment 5: Hybrid — use full pool when candidates large ────────────
    print("\n=== EXPERIMENT 5: Hybrid entropy pool ===")

    def solve_hybrid(
        secret: str,
        answer_words_: list[str],
        guess_words_: list[str],
        opener_: str,
        threshold_direct_: int,
        threshold_full_pool: int,  # use full pool when candidates > this
    ) -> tuple[int, bool]:
        constraints = SolverConstraints()
        tried: set[str] = set()
        words_tried: list[str] = []
        for turn in range(MAX_TURNS):
            candidates = [w for w in answer_words_ if constraints.candidate_matches(w)]
            if not candidates:
                break
            if turn == 0:
                guess = opener_
            elif len(candidates) <= threshold_direct_:
                guess = next((w for w in candidates if w not in tried), None)
                if guess is None:
                    break
            else:
                pool_ = guess_words_ if len(candidates) > threshold_full_pool else answer_words_
                guess = _best_entropy_from_pool(pool_, candidates, tried)
            tried.add(guess)
            words_tried.append(guess)
            sc = score_guess(secret, guess)
            if all(v == 2 for v in sc):
                return len(words_tried), True
            constraints.update(guess, sc)
        return len(words_tried), False

    for thresh_full in [100, 50, 20]:
        t0 = time.perf_counter()
        totals, solved_c, failed_c = 0, 0, 0
        for secret in answer_words:
            turns, solved = solve_hybrid(
                secret, answer_words, guess_words, best_opener,
                threshold_direct_=4, threshold_full_pool=thresh_full,
            )
            totals += turns
            if solved:
                solved_c += 1
            else:
                failed_c += 1
        avg = totals / solved_c if solved_c else 999.0
        elapsed = time.perf_counter() - t0
        print(f"  full_pool_when_cands>{thresh_full:4d}  avg={avg:.4f}  "
              f"solve={solved_c/len(answer_words):.3%}  "
              f"failed={failed_c}  time={elapsed:.1f}s")

    # ── Experiment 6: Scan ALL answer words as openers for best pick ──────────
    print("\n=== EXPERIMENT 6: Full scan of all answer words as opener ===")
    t0 = time.perf_counter()
    all_answer_scores = rank_openers(answer_words, answer_words, top_n=len(answer_words))
    elapsed = time.perf_counter() - t0
    print(f"Scored all {len(answer_words)} answer words in {elapsed:.1f}s")
    print("Top 10:")
    for word, h in all_answer_scores[:10]:
        print(f"  {word}: {h:.4f} bits")

    absolute_best = all_answer_scores[0][0]

    # Run final full benchmark with absolute best opener
    print(f"\n=== FINAL: Full benchmark with best opener '{absolute_best}' ===")
    for thresh in [3, 4, 5]:
        t0 = time.perf_counter()
        stats = benchmark(answer_words, answer_words, guess_words, absolute_best,
                          threshold_direct=thresh, entropy_pool="answer")
        elapsed = time.perf_counter() - t0
        print(f"  threshold={thresh}  avg={stats['avg_turns']:.4f}  "
              f"solve={stats['solve_rate']:.3%}  failed={stats['failed']}  "
              f"time={elapsed:.1f}s")
        if stats['failures']:
            print(f"  failures: {stats['failures'][:5]}")

    print("\n=== SUMMARY ===")
    print(f"Recommended opener: {absolute_best}")
    print(f"Best opener by entropy (bits): {all_answer_scores[0]}")


if __name__ == "__main__":
    main()
