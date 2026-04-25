"""Data loading and validation utilities."""

from __future__ import annotations

from csv import DictReader
from dataclasses import dataclass
from pathlib import Path
import random

from wordle.constants import DEFAULT_DATASET_PATH, DEFAULT_GUESS_PATH


@dataclass(frozen=True)
class WordleData:
    guess_words: tuple[str, ...]
    official_answers: tuple[str, ...]

    @property
    def guess_word_set(self) -> set[str]:
        return set(self.guess_words)


def load_guess_words(path: Path = DEFAULT_GUESS_PATH) -> tuple[str, ...]:
    words = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            word = line.strip().lower()
            if len(word) == 5 and word.isalpha():
                words.append(word)
    return tuple(dict.fromkeys(words))


def load_official_answers(path: Path = DEFAULT_DATASET_PATH) -> tuple[str, ...]:
    answers = []
    with path.open("r", encoding="utf-8") as file:
        reader = DictReader(file)
        for row in reader:
            word = (row.get("word") or "").strip().lower()
            day = (row.get("day") or "").strip()
            if day and len(word) == 5 and word.isalpha():
                answers.append(word)
    return tuple(dict.fromkeys(answers))


def load_wordle_data(
    guess_path: Path = DEFAULT_GUESS_PATH,
    dataset_path: Path = DEFAULT_DATASET_PATH,
) -> WordleData:
    return WordleData(
        guess_words=load_guess_words(guess_path),
        official_answers=load_official_answers(dataset_path),
    )


def find_missing_answers(data: WordleData) -> list[str]:
    guess_set = data.guess_word_set
    return sorted(word for word in data.official_answers if word not in guess_set)


def choose_random_answer(data: WordleData, rng: random.Random | None = None) -> str:
    if not data.official_answers:
        raise ValueError("official answer list is empty")
    randomizer = rng or random
    return randomizer.choice(data.official_answers)
