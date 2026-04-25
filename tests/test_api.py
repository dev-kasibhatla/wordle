from fastapi.testclient import TestClient

import pytest

from wordle.api.app import create_app, _GAME_LIMITER, _SOLVER_LIMITER
from wordle.data import WordleData


TEST_GUESSES = ("cigar", "rebut", "sissy", "humph", "awake", "serve", "crane")
TEST_ANSWERS = ("cigar", "awake", "serve")


@pytest.fixture(autouse=True)
def _reset_limiters():
    """Reset in-memory rate limiter state between tests to prevent leakage."""
    _GAME_LIMITER._ip.clear()
    _GAME_LIMITER._all.clear()
    _SOLVER_LIMITER._ip.clear()
    _SOLVER_LIMITER._all.clear()
    yield
    _GAME_LIMITER._ip.clear()
    _GAME_LIMITER._all.clear()
    _SOLVER_LIMITER._ip.clear()
    _SOLVER_LIMITER._all.clear()


def _client(seed: int = 0) -> TestClient:
    app = create_app(data=WordleData(guess_words=TEST_GUESSES, official_answers=TEST_ANSWERS), seed=seed)
    return TestClient(app)


# ── legacy shim ───────────────────────────────────────────────────────────────

def test_new_game_returns_game_id_and_status():
    client = _client()
    response = client.post("/wordle/play", json={"action": "new"})
    payload = response.json()
    assert payload["status"] == "in_progress"
    assert payload["game_id"]
    assert payload["turn"] == 0


def test_guess_flow_updates_history():
    client = _client()
    new_game = client.post("/wordle/play", json={"action": "new"}).json()
    game_id = new_game["game_id"]

    guess_response = client.post(
        "/wordle/play",
        json={"action": "guess", "game_id": game_id, "guess": "cigar"},
    )
    payload = guess_response.json()
    assert payload["turn"] == 1
    assert len(payload["history"]) == 1


def test_guess_requires_game_id():
    client = _client()
    response = client.post("/wordle/play", json={"action": "guess", "guess": "cigar"})
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_game_id"


# ── /api/games ────────────────────────────────────────────────────────────────

def test_create_game_returns_game_id():
    client = _client()
    res = client.post("/api/games")
    assert res.status_code == 201
    data = res.json()
    assert data["game_id"]
    assert data["status"] == "in_progress"
    assert data["turn"] == 0
    assert data["history"] == []


def test_get_game_returns_state():
    client = _client()
    game_id = client.post("/api/games").json()["game_id"]
    res = client.get(f"/api/games/{game_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["game_id"] == game_id
    assert data["status"] == "in_progress"


def test_get_game_unknown_returns_404():
    client = _client()
    res = client.get("/api/games/nonexistent-id")
    assert res.status_code == 404


def test_submit_guess_updates_turn():
    client = _client()
    game_id = client.post("/api/games").json()["game_id"]
    res = client.post(f"/api/games/{game_id}/guesses", json={"guess": "cigar"})
    assert res.status_code == 200
    data = res.json()
    assert data["turn"] == 1
    assert data["guess"] == "cigar"
    assert len(data["score"]) == 5
    assert len(data["history"]) == 1


def test_submit_invalid_word_returns_422():
    client = _client()
    game_id = client.post("/api/games").json()["game_id"]
    res = client.post(f"/api/games/{game_id}/guesses", json={"guess": "zzzzz"})
    assert res.status_code == 422


def test_solved_game_reveals_secret():
    # seed=0 picks cigar as first answer
    client = _client(seed=0)
    game_id = client.post("/api/games").json()["game_id"]
    # Try to win: keep guessing known words until status is solved or failed
    for word in TEST_GUESSES:
        res = client.post(f"/api/games/{game_id}/guesses", json={"guess": word})
        data = res.json()
        if data["status"] in ("solved", "failed"):
            assert data["secret"] is not None
            break


# ── /api/solver/run ───────────────────────────────────────────────────────────

def test_solver_run_returns_turns():
    client = _client()
    res = client.post("/api/solver/run", json={"secret": "cigar", "mode": "a"})
    assert res.status_code == 200
    data = res.json()
    assert data["secret"] == "cigar"
    assert data["mode"] == "a"
    assert isinstance(data["turns"], list)
    assert len(data["turns"]) >= 1


def test_solver_run_mode_b_all_hail_mary():
    client = _client()
    res = client.post("/api/solver/run", json={"secret": "awake", "mode": "b"})
    assert res.status_code == 200
    data = res.json()
    for turn in data["turns"]:
        assert turn["mode"] == "hail_mary"


def test_solver_run_unknown_word_returns_422():
    client = _client()
    res = client.post("/api/solver/run", json={"secret": "zxqvw"})
    assert res.status_code == 422


# ── /api/solver/analyze ───────────────────────────────────────────────────────

def test_solver_analyze_returns_candidates():
    client = _client()
    res = client.post("/api/solver/analyze", json={
        "history": [{"guess": "cigar", "score": [2, 0, 0, 0, 0]}],
        "mode": "a",
    })
    assert res.status_code == 200
    data = res.json()
    assert "candidates_remaining" in data
    assert isinstance(data["candidates_remaining"], int)
    assert data["candidates_remaining"] >= 0


def test_solver_analyze_with_secret_returns_auto_finish():
    client = _client()
    # Empty history leaves all candidates open; solver auto-finishes from blank state
    res = client.post("/api/solver/analyze", json={
        "history": [],
        "mode": "a",
        "secret": "awake",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["auto_finish"] is not None
    assert isinstance(data["auto_finish"]["turns"], list)
    assert len(data["auto_finish"]["turns"]) >= 1


def test_solver_analyze_no_history():
    client = _client()
    res = client.post("/api/solver/analyze", json={"history": [], "mode": "a"})
    assert res.status_code == 200
    data = res.json()
    assert data["candidates_remaining"] == len(TEST_ANSWERS)


# ── rate limiting ─────────────────────────────────────────────────────────────

def test_rate_limit_per_ip_triggers():
    from wordle.api.app import _GAME_LIMITER
    # patch the per_ip limit to 1 for this test
    original = _GAME_LIMITER._per_ip
    _GAME_LIMITER._per_ip = 1
    _GAME_LIMITER._ip.clear()
    _GAME_LIMITER._all.clear()
    try:
        client = _client()
        r1 = client.post("/api/games")
        r2 = client.post("/api/games")
        assert r1.status_code == 201
        assert r2.status_code == 429
        err = r2.json()
        assert err["detail"]["code"] == "rate_limit_ip"
    finally:
        _GAME_LIMITER._per_ip = original
        _GAME_LIMITER._ip.clear()
        _GAME_LIMITER._all.clear()


def test_rate_limit_global_triggers():
    from wordle.api.app import _GAME_LIMITER
    original = _GAME_LIMITER._global
    _GAME_LIMITER._global = 1
    _GAME_LIMITER._per_ip = 1000
    _GAME_LIMITER._ip.clear()
    _GAME_LIMITER._all.clear()
    try:
        client = _client()
        # Use two different mock IPs by patching the client host
        r1 = client.post("/api/games", headers={"x-forwarded-for": "1.1.1.1"})
        r2 = client.post("/api/games", headers={"x-forwarded-for": "2.2.2.2"})
        assert r1.status_code == 201
        assert r2.status_code == 429
        err = r2.json()
        assert err["detail"]["code"] == "rate_limit_global"
    finally:
        _GAME_LIMITER._global = original
        _GAME_LIMITER._per_ip = 30
        _GAME_LIMITER._ip.clear()
        _GAME_LIMITER._all.clear()

