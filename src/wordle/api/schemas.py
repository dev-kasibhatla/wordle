"""Request and response schemas for API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlayRequest(BaseModel):
    action: str = Field(pattern="^(new|guess)$")
    game_id: str | None = None
    guess: str | None = None


class GuessHistoryItem(BaseModel):
    guess: str
    score: list[int]


class ErrorPayload(BaseModel):
    code: str
    message: str


class PlayResponse(BaseModel):
    game_id: str | None = None
    status: str
    turn: int = 0
    turns_remaining: int = 0
    history: list[GuessHistoryItem] = []
    latest: GuessHistoryItem | None = None
    error: ErrorPayload | None = None
