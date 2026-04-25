"""Game state and rule enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field

from wordle.constants import MAX_TURNS, WORD_LENGTH
from wordle.engine import score_guess
from wordle.errors import WordleRuleError


@dataclass(frozen=True)
class GuessFeedback:
    guess: str
    score: list[int]


@dataclass
class GameState:
    secret: str
    turn: int = 0
    history: list[GuessFeedback] = field(default_factory=list)
    solved: bool = False
    failed: bool = False

    @property
    def status(self) -> str:
        if self.solved:
            return "solved"
        if self.failed:
            return "failed"
        return "in_progress"

    @property
    def turns_remaining(self) -> int:
        return max(0, MAX_TURNS - self.turn)


class WordleGameEngine:
    """Stateful helper for applying validated guesses."""

    def __init__(self, guess_words: set[str]) -> None:
        self.guess_words = guess_words

    def validate_guess(self, guess: str) -> str:
        normalized = guess.lower().strip()
        if len(normalized) != WORD_LENGTH or not normalized.isalpha():
            raise WordleRuleError("invalid_length", "guess must be a 5-letter word")
        if normalized not in self.guess_words:
            raise WordleRuleError("unknown_word", "guess is not in dictionary")
        return normalized

    def apply_guess(self, state: GameState, guess: str) -> GuessFeedback:
        if state.solved or state.failed or state.turn >= MAX_TURNS:
            raise WordleRuleError("game_over", "cannot guess after game completion")

        normalized = self.validate_guess(guess)
        score = score_guess(state.secret, normalized)
        feedback = GuessFeedback(guess=normalized, score=score)

        state.history.append(feedback)
        state.turn += 1
        state.solved = all(value == 2 for value in score)
        state.failed = not state.solved and state.turn >= MAX_TURNS
        return feedback
