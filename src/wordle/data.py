"""Data loading and validation utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import random

from wordle.constants import DEFAULT_WORDS_PATH, DEFAULT_GUESSES_PATH


@dataclass(frozen=True)
class WordleData:
    """Dual-source word data: answers come from words.txt, guesses from both files."""

    # All valid guess words (answers + extended guess list) for gameplay and investigate phase.
    guess_words: tuple[str, ...]
    # Only words eligible to be the secret answer (from words.txt).
    official_answers: tuple[str, ...]
    # Frozenset for O(1) membership checks; computed once from guess_words.
    _word_set: frozenset[str] = field(default_factory=frozenset, init=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_word_set", frozenset(self.guess_words))

    @property
    def guess_word_set(self) -> frozenset[str]:
        return self._word_set


def load_words(path: Path) -> tuple[str, ...]:
    """Load and deduplicate 5-letter words from a plain word-per-line file."""
    seen: set[str] = set()
    words: list[str] = []
    with path.open("r", encoding="utf-8", buffering=1 << 20) as fh:
        for line in fh:
            w = line.strip().lower()
            if len(w) == 5 and w.isalpha() and w not in seen:
                seen.add(w)
                words.append(w)
    return tuple(words)


def load_wordle_data(
    answers_path: Path = DEFAULT_WORDS_PATH,
    guesses_path: Path = DEFAULT_GUESSES_PATH,
) -> WordleData:
    """Load WordleData from separate answers and extended guess list files.

    Answers (words.txt) are the only valid secrets.
    Guess words = answers union allowed-guesses, used for gameplay and investigate phase.
    """
    answer_words = load_words(answers_path)
    guess_only_words = load_words(guesses_path)
    answer_set = set(answer_words)
    # Merge: answers first (preserve order), then extra guess-only words
    combined: list[str] = list(answer_words)
    for w in guess_only_words:
        if w not in answer_set:
            combined.append(w)
    return WordleData(guess_words=tuple(combined), official_answers=answer_words)


def find_missing_answers(data: WordleData) -> list[str]:
    """Return any official answers absent from the guess dictionary."""
    return sorted(w for w in data.official_answers if w not in data.guess_word_set)


def choose_random_answer(data: WordleData, rng: random.Random | None = None) -> str:
    if not data.official_answers:
        raise ValueError("official answer list is empty")
    randomizer = rng or random
    return randomizer.choice(data.official_answers)
