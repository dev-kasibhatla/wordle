"""Two-mode solver strategy."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from wordle.constants import MAX_TURNS, WORD_LENGTH
from wordle.engine import score_guess
from wordle.solver.constraints import SolverConstraints


@dataclass(frozen=True)
class SolverConfig:
    mode: str = "a"
    investigate_limit: int = 3
    # Switch to hail_mary when we've confirmed this many distinct letters
    threshold_known_letters: int = 4
    # Switch to hail_mary when this many positions are locked (green)
    threshold_locked_positions: int = 3
    # Switch to hail_mary when candidates fall at or below this count
    threshold_candidate_count: int = 15
    # Mode A only: use a separator guess from the full pool when hail_mary has
    # more than this many candidates (prevents sequential exhaustion of rhyme clusters).
    threshold_separator: int = 2


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
    constraints: SolverConstraints | None = None,
) -> str:
    """Pick the best information-gathering guess from the full allowed-guess pool.

    Prefers words with all-unique letters. Strongly scores letters not yet
    confirmed, since already-known letters yield zero new information.
    """
    frequencies = _build_letter_frequencies(candidates)

    # Letters already known from previous guesses — contribute little new info.
    known_letters: set[str] = set()
    if constraints is not None:
        known_letters = (
            set(constraints.min_counts.keys()) | set(constraints.fixed_positions.values())
        )

    best_word = ""
    best_score = -1

    for word in guess_words:
        if word in tried:
            continue
        letters = set(word)
        # Large bonus for having all distinct letters; each duplicate dilutes value.
        score = len(letters) * 100
        for char in letters:
            freq = frequencies.get(char, 0)
            # Unknown letters deliver full information value; known ones are worth
            # a fraction since their presence is already confirmed.
            if char not in known_letters:
                score += freq * 2
            else:
                score += freq // 4
        if score > best_score:
            best_word = word
            best_score = score

    if best_word:
        return best_word

    # Fallback: return any untried guess word
    for word in guess_words:
        if word not in tried:
            return word
    raise RuntimeError("no valid investigate guess available")


def _select_separator_guess(
    guess_words: list[str],
    candidates: list[str],
    tried: set[str],
) -> str:
    """Pick a guess that tests the most variable letters across remaining candidates.

    Used in mode A when hail_mary mode still has many candidates. Searches the
    full guess pool so it can find words covering many variable positions at once.
    Gives a bonus to words that are themselves answer candidates.
    """
    candidate_set = set(candidates)
    frequencies = _build_letter_frequencies(candidates)

    # Letters that differ across candidate positions — the key information targets.
    variable_letters: set[str] = set()
    for pos in range(WORD_LENGTH):
        pos_letters = {word[pos] for word in candidates}
        if len(pos_letters) > 1:
            variable_letters.update(pos_letters)

    best_word = ""
    best_score = -1

    for word in guess_words:
        if word in tried:
            continue
        letters = set(word)
        covered_variable = letters & variable_letters
        # Primary: unique variable letters covered, weighted by candidate frequency.
        score = len(covered_variable) * 200
        for char in covered_variable:
            score += frequencies.get(char, 0)
        # Secondary: total unique letters (any extra info helps).
        score += len(letters) * 10
        # Bonus: the word is itself a candidate — it could solve directly.
        if word in candidate_set:
            score += 50
        if score > best_score:
            best_word = word
            best_score = score

    if best_word:
        return best_word
    return _select_hail_mary_guess(candidates, tried)


def _select_hail_mary_guess(candidates: list[str], tried: set[str]) -> str:
    """Pick the next untried candidate from the answer-eligible list."""
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
    """Return True when investigate phase should end and hail mary begin."""
    if config.mode == "b":
        return True
    # After 3 investigate turns the strategy always commits to hail mary.
    if turn >= config.investigate_limit:
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
    """Solve a Wordle puzzle.

    guess_words: full allowed-guess pool (used during investigate phase).
    answer_words: answer-eligible words only (used during hail_mary phase and
                  for tracking remaining candidates).
    """
    cfg = config or SolverConfig()
    if cfg.mode not in {"a", "b"}:
        raise ValueError("solver mode must be 'a' or 'b'")

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
            # Mode A: use a separator when too many candidates remain to guess
            # sequentially within the remaining turns budget.
            if cfg.mode == "a" and len(candidates) > cfg.threshold_separator:
                guess = _select_separator_guess(guess_words, candidates, tried)
            else:
                guess = _select_hail_mary_guess(candidates, tried)
        else:
            guess = _select_investigate_guess(guess_words, tried, candidates, constraints)

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
