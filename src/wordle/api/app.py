"""FastAPI application factory."""

from __future__ import annotations

import time
from collections import defaultdict
from importlib.metadata import version as _pkg_version
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    APP_VERSION: str = _pkg_version("wordle")
except Exception:
    APP_VERSION = "dev"

from wordle.api.schemas import (
    AnalyzeGuessItem,
    ErrorPayload,
    GameStateResponse,
    GuessHistoryItem,
    GuessRequest,
    GuessResponse,
    PlayRequest,
    PlayResponse,
    SolverAnalyzeRequest,
    SolverAnalyzeResponse,
    SolverRunRequest,
    SolverRunResponse,
    SolverTurn,
)
from wordle.data import WordleData, load_wordle_data
from wordle.errors import WordleRuleError
from wordle.service import GameManager, PlayResult, SolverResult
from wordle.solver.strategy import SolverConfig

# ── rate limiting (in-memory, single-process) ─────────────────────────────────

_WINDOW = 60  # seconds

class _Limiter:
    def __init__(self, per_ip: int, global_: int) -> None:
        self._per_ip = per_ip
        self._global = global_
        self._ip: dict[str, list[float]] = defaultdict(list)
        self._all: list[float] = []

    def check(self, ip: str) -> None:
        now = time.monotonic()
        cutoff = now - _WINDOW
        self._all = [t for t in self._all if t > cutoff]
        self._ip[ip] = [t for t in self._ip[ip] if t > cutoff]
        if len(self._all) >= self._global:
            raise HTTPException(status_code=429, detail={"code": "rate_limit_global", "message": "Server is busy. Try again shortly."})
        if len(self._ip[ip]) >= self._per_ip:
            raise HTTPException(status_code=429, detail={"code": "rate_limit_ip", "message": "Too many requests. Slow down."})
        self._all.append(now)
        self._ip[ip].append(now)


_GAME_LIMITER = _Limiter(per_ip=30, global_=300)    # play requests
_SOLVER_LIMITER = _Limiter(per_ip=10, global_=60)   # solver requests (heavier)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


# ── helper converters ─────────────────────────────────────────────────────────

def _to_play_response(result: PlayResult) -> PlayResponse:
    history = [GuessHistoryItem(guess=i.guess, score=i.score) for i in result.state.history]
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


def _to_game_state(game_id: str, result: PlayResult, *, reveal_secret: bool = False) -> GameStateResponse:
    history = [GuessHistoryItem(guess=i.guess, score=i.score) for i in result.state.history]
    terminal = result.state.status in ("solved", "failed")
    return GameStateResponse(
        game_id=game_id,
        status=result.state.status,
        turn=result.state.turn,
        turns_remaining=result.state.turns_remaining,
        history=history,
        secret=result.state.secret if (reveal_secret and terminal) else None,
    )


def _solver_result_to_response(secret: str, mode: str, result: SolverResult) -> SolverRunResponse:
    turns = [
        SolverTurn(
            turn=t.turn,
            guess=t.guess,
            score=t.score,
            mode=t.mode,
            candidates_remaining=t.candidates_remaining,
        )
        for t in result.turns
    ]
    return SolverRunResponse(
        secret=secret,
        mode=mode,
        solved=result.solved,
        turns_taken=result.turns_taken,
        turns=turns,
    )


# ── API router ────────────────────────────────────────────────────────────────

def _make_router(app: FastAPI) -> APIRouter:
    router = APIRouter(prefix="/api")

    # -- version ---------------------------------------------------------------

    @router.get("/version")
    def get_version() -> dict:
        return {"version": APP_VERSION}

    # -- game endpoints --------------------------------------------------------

    @router.post("/games", response_model=GameStateResponse, status_code=201)
    def create_game(request: Request) -> GameStateResponse:
        _GAME_LIMITER.check(_client_ip(request))
        manager: GameManager = app.state.manager
        result = manager.new_game()
        return GameStateResponse(
            game_id=result.game_id,
            status=result.state.status,
            turn=result.state.turn,
            turns_remaining=result.state.turns_remaining,
            history=[],
        )

    @router.get("/games/{game_id}", response_model=GameStateResponse)
    def get_game(game_id: str, request: Request) -> GameStateResponse:
        _GAME_LIMITER.check(_client_ip(request))
        manager: GameManager = app.state.manager
        try:
            state = manager.get_game(game_id)
        except WordleRuleError as e:
            raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
        terminal = state.status in ("solved", "failed")
        return GameStateResponse(
            game_id=game_id,
            status=state.status,
            turn=state.turn,
            turns_remaining=state.turns_remaining,
            history=[GuessHistoryItem(guess=i.guess, score=i.score) for i in state.history],
            secret=state.secret if terminal else None,
        )

    @router.post("/games/{game_id}/guesses", response_model=GuessResponse)
    def submit_guess(game_id: str, body: GuessRequest, request: Request) -> GuessResponse:
        _GAME_LIMITER.check(_client_ip(request))
        manager: GameManager = app.state.manager
        try:
            result = manager.play_guess(game_id, body.guess)
        except WordleRuleError as e:
            raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
        terminal = result.state.status in ("solved", "failed")
        return GuessResponse(
            game_id=game_id,
            status=result.state.status,
            turn=result.state.turn,
            turns_remaining=result.state.turns_remaining,
            guess=result.latest[0] if result.latest else body.guess,
            score=result.latest[1] if result.latest else [],
            history=[GuessHistoryItem(guess=i.guess, score=i.score) for i in result.state.history],
            secret=result.state.secret if terminal else None,
        )

    # -- solver endpoints ------------------------------------------------------

    @router.post("/solver/run", response_model=SolverRunResponse)
    def solver_run(body: SolverRunRequest, request: Request) -> SolverRunResponse:
        _SOLVER_LIMITER.check(_client_ip(request))
        manager: GameManager = app.state.manager
        config = SolverConfig(mode=body.mode)
        try:
            result = manager.run_solver(body.secret.lower().strip(), config)
        except WordleRuleError as e:
            raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
        return _solver_result_to_response(body.secret.lower().strip(), body.mode, result)

    @router.post("/solver/analyze", response_model=SolverAnalyzeResponse)
    def solver_analyze(body: SolverAnalyzeRequest, request: Request) -> SolverAnalyzeResponse:
        _SOLVER_LIMITER.check(_client_ip(request))
        manager: GameManager = app.state.manager
        config = SolverConfig(mode=body.mode)
        history = [(item.guess.lower().strip(), item.score) for item in body.history]
        secret = body.secret.lower().strip() if body.secret else None
        try:
            candidates, suggestion, suggestion_mode, auto_finish_result = manager.analyze_state(
                history, config, secret
            )
        except WordleRuleError as e:
            raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
        auto_finish = None
        if auto_finish_result is not None and secret is not None:
            auto_finish = _solver_result_to_response(secret, body.mode, auto_finish_result)
        return SolverAnalyzeResponse(
            candidates_remaining=candidates,
            suggestion=suggestion,
            suggestion_mode=suggestion_mode,
            auto_finish=auto_finish,
        )

    return router


# ── app factory ───────────────────────────────────────────────────────────────

def create_app(data: WordleData | None = None, seed: int | None = None) -> FastAPI:
    app = FastAPI(title="Wordle", version=APP_VERSION, docs_url="/api/docs", redoc_url=None)
    app.state.manager = GameManager(data or load_wordle_data(), seed=seed)

    # mount API router
    app.include_router(_make_router(app))

    # legacy shim preserved for old tests
    @app.post("/wordle/play", response_model=PlayResponse, include_in_schema=False)
    def play(body: PlayRequest) -> PlayResponse:
        manager: GameManager = app.state.manager
        try:
            if body.action == "new":
                return _to_play_response(manager.new_game())
            if not body.game_id:
                raise WordleRuleError("missing_game_id", "game_id is required for guess action")
            if not body.guess:
                raise WordleRuleError("missing_guess", "guess is required for guess action")
            return _to_play_response(manager.play_guess(body.game_id, body.guess))
        except WordleRuleError as error:
            return PlayResponse(status="error", error=ErrorPayload(code=error.code, message=error.message))

    # static UI
    static_dir = Path(__file__).resolve().parents[3] / "static"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(str(static_dir / "index.html"))

    return app
