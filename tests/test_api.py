from fastapi.testclient import TestClient

from wordle.api.app import create_app
from wordle.data import WordleData


TEST_GUESSES = ("cigar", "rebut", "sissy", "humph", "awake")
TEST_ANSWERS = ("cigar", "awake")


def _client() -> TestClient:
    app = create_app(data=WordleData(guess_words=TEST_GUESSES, official_answers=TEST_ANSWERS), seed=0)
    return TestClient(app)


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
