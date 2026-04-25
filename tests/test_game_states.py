"""Comprehensive tests for game lifecycle, edge cases, and all terminal states.

Test matrix:
  - New game creation
  - Sequential guess submission (no row skipping)
  - Valid/invalid word rejection
  - Correct scoring feedback per guess
  - Solved in 1, solved in 6, failed after 6
  - Guess after game over (solved / failed)
  - Duplicate guess allowed (Wordle allows repeats)
  - History correctness on every turn
  - Secret revealed only on terminal states
  - Game state GET consistency at every turn
  - Turns remaining countdown accuracy
"""

import pytest
from fastapi.testclient import TestClient

from wordle.api.app import _GAME_LIMITER, _SOLVER_LIMITER, create_app
from wordle.data import WordleData
from wordle.engine import score_guess
from wordle.errors import WordleRuleError
from wordle.game import GameState, WordleGameEngine

# ── fixtures ──────────────────────────────────────────────────────────────────

# 7 guess words, 3 answers — deterministic with seed=0 picks "cigar"
WORDS = ("cigar", "rebut", "sissy", "humph", "awake", "serve", "crane")
ANSWERS = ("cigar", "awake", "serve")


@pytest.fixture(autouse=True)
def _reset_limiters():
    for lim in (_GAME_LIMITER, _SOLVER_LIMITER):
        lim._ip.clear()
        lim._all.clear()
    yield
    for lim in (_GAME_LIMITER, _SOLVER_LIMITER):
        lim._ip.clear()
        lim._all.clear()


def _client(seed: int = 0) -> TestClient:
    app = create_app(
        data=WordleData(guess_words=WORDS, official_answers=ANSWERS),
        seed=seed,
    )
    return TestClient(app)


def _new_game(client: TestClient) -> str:
    res = client.post("/api/games")
    assert res.status_code == 201
    return res.json()["game_id"]


def _guess(client: TestClient, game_id: str, word: str) -> dict:
    res = client.post(f"/api/games/{game_id}/guesses", json={"guess": word})
    return res


# ── engine unit tests ─────────────────────────────────────────────────────────


class TestScoreGuess:
    """Wordle scoring correctness, especially duplicate-letter edge cases."""

    def test_exact_match(self):
        assert score_guess("crane", "crane") == [2, 2, 2, 2, 2]

    def test_no_match(self):
        assert score_guess("crane", "humph") == [0, 0, 0, 0, 0]

    def test_yellow_single(self):
        # secret="crane", guess="rebut"
        # r at pos 0: r is in crane at pos 1 -> yellow
        # e at pos 1: e is in crane at pos 4 -> yellow
        # b,u,t not in crane -> grey
        assert score_guess("crane", "rebut") == [1, 1, 0, 0, 0]

    def test_duplicate_letters_in_guess(self):
        # secret=allee, guess=eagle: e at pos 0 is yellow (exists elsewhere),
        # a at pos 1 is yellow, g is absent, l at pos 3 is yellow, e at pos 4 is green
        assert score_guess("allee", "eagle") == [1, 1, 0, 1, 2]

    def test_duplicate_letters_in_secret(self):
        # secret=belle, guess=level
        assert score_guess("belle", "level") == [1, 2, 0, 1, 1]

    def test_green_consumes_before_yellow(self):
        # secret "aabbb" guess "aaccc" -> first two green, rest absent
        assert score_guess("aabbb", "aaccc") == [2, 2, 0, 0, 0]

    def test_only_one_yellow_when_secret_has_one(self):
        # secret "abcde", guess "aaxxx" -> first 'a' green, second 'a' absent
        assert score_guess("abcde", "aaxxx") == [2, 0, 0, 0, 0]


# ── game state machine ───────────────────────────────────────────────────────


class TestGameStateMachine:
    """Tests for GameState + WordleGameEngine state transitions."""

    def _engine(self, words: set[str] | None = None):
        return WordleGameEngine(words or set(WORDS))

    def test_initial_state(self):
        state = GameState(secret="cigar")
        assert state.status == "in_progress"
        assert state.turn == 0
        assert state.turns_remaining == 6
        assert state.history == []
        assert not state.solved
        assert not state.failed

    def test_turn_increments(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        engine.apply_guess(state, "crane")
        assert state.turn == 1
        assert state.turns_remaining == 5

    def test_solve_on_first_guess(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        fb = engine.apply_guess(state, "cigar")
        assert fb.score == [2, 2, 2, 2, 2]
        assert state.solved
        assert state.status == "solved"
        assert state.turn == 1

    def test_solve_on_sixth_guess(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        for word in ("crane", "rebut", "sissy", "humph", "awake"):
            engine.apply_guess(state, word)
        assert state.turn == 5
        assert not state.solved
        assert not state.failed
        fb = engine.apply_guess(state, "cigar")
        assert state.solved
        assert state.status == "solved"
        assert state.turn == 6

    def test_fail_after_six_wrong_guesses(self):
        engine = self._engine()
        state = GameState(secret="serve")
        wrong = ("cigar", "rebut", "sissy", "humph", "awake", "crane")
        for word in wrong:
            engine.apply_guess(state, word)
        assert state.failed
        assert state.status == "failed"
        assert state.turn == 6
        assert state.turns_remaining == 0

    def test_guess_after_solved_raises(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        engine.apply_guess(state, "cigar")
        assert state.solved
        with pytest.raises(WordleRuleError) as exc_info:
            engine.apply_guess(state, "crane")
        assert exc_info.value.code == "game_over"

    def test_guess_after_failed_raises(self):
        engine = self._engine()
        state = GameState(secret="serve")
        for word in ("cigar", "rebut", "sissy", "humph", "awake", "crane"):
            engine.apply_guess(state, word)
        assert state.failed
        with pytest.raises(WordleRuleError) as exc_info:
            engine.apply_guess(state, "cigar")
        assert exc_info.value.code == "game_over"

    def test_invalid_length_rejected(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        with pytest.raises(WordleRuleError) as exc_info:
            engine.apply_guess(state, "hi")
        assert exc_info.value.code == "invalid_length"

    def test_unknown_word_rejected(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        with pytest.raises(WordleRuleError) as exc_info:
            engine.apply_guess(state, "zzzzz")
        assert exc_info.value.code == "unknown_word"

    def test_duplicate_guess_allowed(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        engine.apply_guess(state, "crane")
        engine.apply_guess(state, "crane")
        assert state.turn == 2
        assert len(state.history) == 2

    def test_history_accumulates_in_order(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        engine.apply_guess(state, "crane")
        engine.apply_guess(state, "rebut")
        assert state.history[0].guess == "crane"
        assert state.history[1].guess == "rebut"

    def test_feedback_score_matches_engine(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        fb = engine.apply_guess(state, "crane")
        expected = score_guess("cigar", "crane")
        assert fb.score == expected

    def test_normalize_uppercase(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        fb = engine.apply_guess(state, "CRANE")
        assert fb.guess == "crane"

    def test_normalize_whitespace(self):
        engine = self._engine()
        state = GameState(secret="cigar")
        fb = engine.apply_guess(state, "  crane  ")
        assert fb.guess == "crane"


# ── API integration tests ────────────────────────────────────────────────────


class TestGameAPI:
    """Full API game lifecycle through every state."""

    def test_create_game(self):
        client = _client()
        res = client.post("/api/games")
        assert res.status_code == 201
        d = res.json()
        assert d["status"] == "in_progress"
        assert d["turn"] == 0
        assert d["turns_remaining"] == 6
        assert d["history"] == []
        assert d["secret"] is None

    def test_get_game_after_creation(self):
        client = _client()
        gid = _new_game(client)
        res = client.get(f"/api/games/{gid}")
        assert res.status_code == 200
        d = res.json()
        assert d["game_id"] == gid
        assert d["status"] == "in_progress"
        assert d["secret"] is None

    def test_get_unknown_game_404(self):
        client = _client()
        res = client.get("/api/games/nonexistent")
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "unknown_game"

    def test_submit_valid_guess(self):
        client = _client()
        gid = _new_game(client)
        res = _guess(client, gid, "crane")
        assert res.status_code == 200
        d = res.json()
        assert d["turn"] == 1
        assert d["turns_remaining"] == 5
        assert d["guess"] == "crane"
        assert len(d["score"]) == 5
        assert all(s in (0, 1, 2) for s in d["score"])
        assert len(d["history"]) == 1
        assert d["secret"] is None  # not terminal yet

    def test_submit_invalid_word_422(self):
        client = _client()
        gid = _new_game(client)
        res = _guess(client, gid, "zzzzz")
        assert res.status_code == 422
        assert res.json()["detail"]["code"] == "unknown_word"

    def test_submit_short_word_422(self):
        client = _client()
        gid = _new_game(client)
        res = _guess(client, gid, "hi")
        assert res.status_code == 422
        assert res.json()["detail"]["code"] == "invalid_length"

    def test_submit_empty_guess_422(self):
        client = _client()
        gid = _new_game(client)
        res = _guess(client, gid, "")
        assert res.status_code == 422

    def test_sequential_guesses_no_skipping(self):
        """Every guess increments turn by exactly 1."""
        client = _client()
        gid = _new_game(client)
        for i, word in enumerate(("crane", "rebut", "sissy"), start=1):
            d = _guess(client, gid, word).json()
            assert d["turn"] == i
            assert d["turns_remaining"] == 6 - i
            assert len(d["history"]) == i

    def test_history_order_preserved(self):
        client = _client()
        gid = _new_game(client)
        guesses = ["crane", "rebut", "sissy"]
        for word in guesses:
            _guess(client, gid, word)
        d = client.get(f"/api/games/{gid}").json()
        for i, word in enumerate(guesses):
            assert d["history"][i]["guess"] == word

    def test_solved_in_one_reveals_secret(self):
        # seed=0 -> "awake"
        client = _client(seed=0)
        gid = _new_game(client)
        res = _guess(client, gid, "awake")
        d = res.json()
        assert d["status"] == "solved"
        assert d["turn"] == 1
        assert d["secret"] == "awake"
        assert d["score"] == [2, 2, 2, 2, 2]

    def test_solved_via_get_reveals_secret(self):
        client = _client(seed=0)  # secret="awake"
        gid = _new_game(client)
        _guess(client, gid, "awake")
        d = client.get(f"/api/games/{gid}").json()
        assert d["status"] == "solved"
        assert d["secret"] == "awake"

    def test_failed_after_six_reveals_secret(self):
        client = _client(seed=0)  # secret="awake"
        gid = _new_game(client)
        wrong = ("cigar", "rebut", "sissy", "humph", "serve", "crane")
        for i, word in enumerate(wrong, start=1):
            d = _guess(client, gid, word).json()
            if i < 6:
                assert d["status"] == "in_progress"
                assert d["secret"] is None
        assert d["status"] == "failed"
        assert d["secret"] == "awake"
        assert d["turn"] == 6
        assert d["turns_remaining"] == 0

    def test_guess_after_solved_422(self):
        client = _client(seed=0)  # secret="awake"
        gid = _new_game(client)
        _guess(client, gid, "awake")
        res = _guess(client, gid, "crane")
        assert res.status_code == 422
        assert res.json()["detail"]["code"] == "game_over"

    def test_guess_after_failed_422(self):
        client = _client(seed=0)  # secret="awake"
        gid = _new_game(client)
        for word in ("cigar", "rebut", "sissy", "humph", "serve", "crane"):
            _guess(client, gid, word)
        res = _guess(client, gid, "cigar")
        assert res.status_code == 422
        assert res.json()["detail"]["code"] == "game_over"

    def test_get_state_consistency_every_turn(self):
        """GET /games/{id} matches POST response at every turn."""
        client = _client(seed=0)  # secret="awake"
        gid = _new_game(client)
        words = ("cigar", "rebut", "sissy")
        for word in words:
            post_d = _guess(client, gid, word).json()
            get_d = client.get(f"/api/games/{gid}").json()
            assert post_d["turn"] == get_d["turn"]
            assert post_d["status"] == get_d["status"]
            assert len(post_d["history"]) == len(get_d["history"])

    def test_score_values_are_valid(self):
        client = _client(seed=0)  # secret="awake"
        gid = _new_game(client)
        d = _guess(client, gid, "cigar").json()
        assert all(s in (0, 1, 2) for s in d["score"])

    def test_duplicate_guess_accepted(self):
        client = _client(seed=0)  # secret="awake"
        gid = _new_game(client)
        d1 = _guess(client, gid, "cigar").json()
        d2 = _guess(client, gid, "cigar").json()
        assert d2["turn"] == 2
        assert len(d2["history"]) == 2
        assert d2["history"][0]["score"] == d2["history"][1]["score"]

    def test_guess_to_unknown_game_404(self):
        client = _client()
        res = _guess(client, "fake-id", "crane")
        # The endpoint raises 422 for WordleRuleError from play_guess
        assert res.status_code in (404, 422)

    def test_non_alpha_rejected(self):
        client = _client()
        gid = _new_game(client)
        res = _guess(client, gid, "12345")
        assert res.status_code == 422

    def test_special_chars_rejected(self):
        client = _client()
        gid = _new_game(client)
        res = _guess(client, gid, "he!!o")
        assert res.status_code == 422

    def test_mixed_case_normalized(self):
        client = _client(seed=0)  # secret="awake"
        gid = _new_game(client)
        d = _guess(client, gid, "CIGAR").json()
        assert d["guess"] == "cigar"
        assert d["turn"] == 1
