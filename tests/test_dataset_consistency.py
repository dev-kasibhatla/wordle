from wordle.data import find_missing_answers, load_wordle_data


def test_all_official_answers_exist_in_guess_dictionary():
    data = load_wordle_data()
    missing = find_missing_answers(data)
    assert missing == []
