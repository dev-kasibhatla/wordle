from wordle.data import find_missing_answers, load_wordle_data


def test_all_official_answers_exist_in_guess_dictionary():
    data = load_wordle_data()
    missing = find_missing_answers(data)
    assert missing == []


def test_guess_pool_is_superset_of_answers():
    data = load_wordle_data()
    answer_set = set(data.official_answers)
    guess_set = data.guess_word_set
    assert answer_set.issubset(guess_set), "every answer must be a valid guess too"


def test_guess_pool_larger_than_answers():
    data = load_wordle_data()
    assert len(data.guess_words) > len(data.official_answers), (
        "guess pool should contain extended words beyond just the answers"
    )
