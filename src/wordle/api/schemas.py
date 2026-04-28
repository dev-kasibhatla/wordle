"""Request and response schemas for API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── legacy ───────────────────────────────────────────────────────────────────

class PlayRequest(BaseModel):
    action: str = Field(pattern="^(new|guess)$")
    game_id: str | None = None
    guess: str | None = None


# ── shared ────────────────────────────────────────────────────────────────────

class GuessHistoryItem(BaseModel):
    guess: str
    score: list[int]


class ErrorPayload(BaseModel):
    code: str
    message: str


# ── legacy response (kept for shim endpoint) ──────────────────────────────────

class PlayResponse(BaseModel):
    game_id: str | None = None
    status: str
    turn: int = 0
    turns_remaining: int = 0
    history: list[GuessHistoryItem] = []
    latest: GuessHistoryItem | None = None
    error: ErrorPayload | None = None


# ── game API ──────────────────────────────────────────────────────────────────

class GameStateResponse(BaseModel):
    game_id: str
    status: str
    turn: int
    turns_remaining: int
    history: list[GuessHistoryItem]
    secret: str | None = None  # revealed only when status is solved or failed


class GuessRequest(BaseModel):
    guess: str


class GuessResponse(BaseModel):
    game_id: str
    status: str
    turn: int
    turns_remaining: int
    guess: str
    score: list[int]
    history: list[GuessHistoryItem]
    secret: str | None = None  # revealed when game ends


# ── solver API ────────────────────────────────────────────────────────────────

class SolverRunRequest(BaseModel):
    secret: str
    mode: str = Field(default="a", pattern="^(a|b|c)$")


class SolverTurn(BaseModel):
    turn: int
    guess: str
    score: list[int]
    mode: str
    candidates_remaining: int | None = None


class SolverRunResponse(BaseModel):
    secret: str
    mode: str
    solved: bool
    turns_taken: int
    turns: list[SolverTurn]


class AnalyzeGuessItem(BaseModel):
    guess: str
    score: list[int]


class SolverAnalyzeRequest(BaseModel):
    history: list[AnalyzeGuessItem]
    mode: str = Field(default="a", pattern="^(a|b|c)$")
    secret: str | None = None  # if supplied, enables auto-finish


class SolverAnalyzeResponse(BaseModel):
    candidates_remaining: int
    suggestion: str | None
    suggestion_mode: str | None
    auto_finish: SolverRunResponse | None = None  # only when secret supplied
