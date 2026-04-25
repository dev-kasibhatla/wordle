"""Two-mode solver strategy."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from wordle.constants import MAX_TURNS
from wordle.engine import score_guess
from wordle.solver.constraints import SolverConstraints


@dataclass(frozen=True)
class SolverConfig:
    investigate_limit: int = 3
    threshold_known_letters: int = 3
    threshold_locked_positions: int = 2
    threshold_candidate_count: int = 18


@dataclass(frozen=True)
class SolverRunResult:
    words_tried: list[str]
    turns_taken: int
    solved: bool
    mode_trace: list[str]


def _unique_letter_score(word: str, frequencies: dict[str, int]) -> int:
    seen = set()
    value = 0
    for char in word:
        if char not in seen:
            value += frequencies.get(char, 0)
            seen.add(char)
    return value


def _build_letter_frequencies(words: list[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for word in words:
        counts.update(set(word))
    return dict(counts)


def _select_investigate_guess(
    guess_words: list[str],
    tried: set[str],
    candidates: list[str],
) -> str:
    frequencies = _build_letter_frequencies(candidates)
    best_word = ""
    best_score = -1

    for word in guess_words:
        if word in tried:
            continue
        unique_bonus = len(set(word)) * 10
        score = unique_bonus + _unique_letter_score(word, frequencies)
        if score > best_score:
            best_word = word
            best_score = score

    if not best_word:
        for word in guess_words:
            if word not in tried:
                return word
        raise RuntimeError("no valid investigate guess available")
    return best_word


def _select_hail_mary_guess(candidates: list[str], tried: set[str]) -> str:
    for word in candidates:
        if word not in tried:
            return word
    raise RuntimeError("no candidate left for hail mary")


def _should_use_hail_mary(
    turn: int,
    constraints: SolverConstraints,
    candidate_count: int,
    config: SolverConfig,
) -> bool:
    if turn >= 3:
        return True
    known_letters = len(constraints.min_counts)
    locked_positions = len(constraints.fixed_positions)
    return (
        known_letters >= config.threshold_known_letters
        or locked_positions >= config.threshold_locked_positions
        or candidate_count <= config.threshold_candidate_count
    )


def solve_secret(
    secret: str,
    guess_words: list[str],
    answer_words: list[str],
    config: SolverConfig | None = None,
) -> SolverRunResult:
    cfg = config or SolverConfig()
    constraints = SolverConstraints()
    tried: set[str] = set()
    words_tried: list[str] = []
    mode_trace: list[str] = []

    for turn in range(MAX_TURNS):
        candidates = [word for word in answer_words if constraints.candidate_matches(word)]
        if not candidates:
            break

        use_hail_mary = _should_use_hail_mary(turn, constraints, len(candidates), cfg)
        mode = "hail_mary" if use_hail_mary else "investigate"
        mode_trace.append(mode)

        if use_hail_mary:
            guess = _select_hail_mary_guess(candidates, tried)
        else:
            guess = _select_investigate_guess(guess_words, tried, candidates)

        tried.add(guess)
        words_tried.append(guess)
        score = score_guess(secret, guess)

        if all(value == 2 for value in score):
            return SolverRunResult(
                words_tried=words_tried,
                turns_taken=len(words_tried),
                solved=True,
                mode_trace=mode_trace,
            )

        constraints.update(guess, score)

    return SolverRunResult(
        words_tried=words_tried,
        turns_taken=len(words_tried),
        solved=False,
        mode_trace=mode_trace,
    )
