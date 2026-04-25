from wordle.engine import score_guess
from wordle.errors import WordleRuleError
from wordle.game import GameState, WordleGameEngine


def test_score_guess_handles_duplicates_correctly_case_one():
    assert score_guess("allee", "eagle") == [1, 1, 0, 1, 2]


def test_score_guess_handles_duplicates_correctly_case_two():
    assert score_guess("belle", "level") == [1, 2, 0, 1, 1]


def test_game_rejects_invalid_guess_length():
    engine = WordleGameEngine({"apple"})
    state = GameState(secret="apple")
    try:
        engine.apply_guess(state, "app")
        assert False, "expected invalid length error"
    except WordleRuleError as error:
        assert error.code == "invalid_length"


def test_game_rejects_unknown_word():
    engine = WordleGameEngine({"apple"})
    state = GameState(secret="apple")
    try:
        engine.apply_guess(state, "other")
        assert False, "expected unknown word error"
    except WordleRuleError as error:
        assert error.code == "unknown_word"


def test_game_transitions_to_solved():
    engine = WordleGameEngine({"apple"})
    state = GameState(secret="apple")
    feedback = engine.apply_guess(state, "apple")
    assert feedback.score == [2, 2, 2, 2, 2]
    assert state.solved is True
    assert state.status == "solved"
