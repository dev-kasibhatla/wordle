"""Puzzle service and in-memory game management."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4
import random

from wordle.data import WordleData, choose_random_answer
from wordle.errors import WordleRuleError
from wordle.game import GameState, WordleGameEngine


@dataclass(frozen=True)
class PlayResult:
    game_id: str
    state: GameState
    latest: tuple[str, list[int]] | None


class GameManager:
    """Simple in-memory game registry."""

    def __init__(self, data: WordleData, seed: int | None = None) -> None:
        self.data = data
        self.engine = WordleGameEngine(set(data.guess_words))
        self._games: dict[str, GameState] = {}
        self._rng = random.Random(seed)

    def new_game(self) -> PlayResult:
        secret = choose_random_answer(self.data, self._rng)
        game_id = str(uuid4())
        state = GameState(secret=secret)
        self._games[game_id] = state
        return PlayResult(game_id=game_id, state=state, latest=None)

    def play_guess(self, game_id: str, guess: str) -> PlayResult:
        state = self._games.get(game_id)
        if state is None:
            raise WordleRuleError("unknown_game", "game_id not found")
        feedback = self.engine.apply_guess(state, guess)
        return PlayResult(
            game_id=game_id,
            state=state,
            latest=(feedback.guess, feedback.score),
        )
