"""Data loading and validation utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import random

from wordle.constants import DEFAULT_WORDS_PATH


@dataclass(frozen=True)
class WordleData:
    """Single-source word list used for both guess validation and secret selection."""

    # Sorted tuple for deterministic ordering and random.choice compatibility.
    guess_words: tuple[str, ...]
    # Same data — every word is a valid secret and a valid guess.
    official_answers: tuple[str, ...]
    # Frozenset for O(1) membership checks; computed once from guess_words.
    _word_set: frozenset[str] = field(default_factory=frozenset, init=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_word_set", frozenset(self.guess_words))

    @property
    def guess_word_set(self) -> frozenset[str]:
        return self._word_set


def load_words(path: Path = DEFAULT_WORDS_PATH) -> tuple[str, ...]:
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


def load_wordle_data(path: Path = DEFAULT_WORDS_PATH) -> WordleData:
    """Load WordleData from the single canonical word list."""
    words = load_words(path)
    return WordleData(guess_words=words, official_answers=words)


def find_missing_answers(data: WordleData) -> list[str]:
    """Return any official answers absent from the guess dictionary."""
    return sorted(w for w in data.official_answers if w not in data.guess_word_set)


def choose_random_answer(data: WordleData, rng: random.Random | None = None) -> str:
    if not data.official_answers:
        raise ValueError("official answer list is empty")
    randomizer = rng or random
    return randomizer.choice(data.official_answers)
