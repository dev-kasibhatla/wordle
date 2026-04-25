"""FastAPI app exposing one endpoint."""

from __future__ import annotations

from fastapi import FastAPI

from wordle.api.schemas import ErrorPayload, GuessHistoryItem, PlayRequest, PlayResponse
from wordle.data import WordleData, load_wordle_data
from wordle.errors import WordleRuleError
from wordle.service import GameManager, PlayResult


def _to_response(result: PlayResult) -> PlayResponse:
    history = [GuessHistoryItem(guess=item.guess, score=item.score) for item in result.state.history]
    latest = None
    if result.latest:
        latest = GuessHistoryItem(guess=result.latest[0], score=result.latest[1])
    return PlayResponse(
        game_id=result.game_id,
        status=result.state.status,
        turn=result.state.turn,
        turns_remaining=result.state.turns_remaining,
        history=history,
        latest=latest,
    )


def create_app(data: WordleData | None = None, seed: int | None = None) -> FastAPI:
    app = FastAPI(title="Wordle API", version="0.1.0")
    app.state.manager = GameManager(data or load_wordle_data(), seed=seed)

    @app.post("/wordle/play", response_model=PlayResponse)
    def play(request: PlayRequest) -> PlayResponse:
        manager: GameManager = app.state.manager
        try:
            if request.action == "new":
                return _to_response(manager.new_game())
            if not request.game_id:
                raise WordleRuleError("missing_game_id", "game_id is required for guess action")
            if not request.guess:
                raise WordleRuleError("missing_guess", "guess is required for guess action")
            return _to_response(manager.play_guess(request.game_id, request.guess))
        except WordleRuleError as error:
            return PlayResponse(
                status="error",
                error=ErrorPayload(code=error.code, message=error.message),
            )

    return app
