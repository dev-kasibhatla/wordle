from wordle.solver.strategy import SolverConfig, solve_secret

# Separate guess pool (extended) and answer pool (answers only) — mirrors real data split.
ANSWER_WORDS = ["cigar", "awake", "blush", "focal", "evade", "naval", "serve"]
# Extended guess pool includes all answer words plus extra guess-only words.
GUESS_WORDS = ANSWER_WORDS + ["rebut", "sissy", "humph", "crane", "slate", "audio"]


def test_solver_solves_secret_within_six_turns():
    result = solve_secret("cigar", GUESS_WORDS, ANSWER_WORDS)
    assert result.solved is True
    assert 1 <= result.turns_taken <= 6


def test_solver_uses_guess_words_in_investigate_phase():
    # Investigate mode should draw from the full GUESS_WORDS pool, not just answers.
    result = solve_secret("serve", GUESS_WORDS, ANSWER_WORDS)
    assert result.solved is True
    # Any investigate-phase guess may come from GUESS_WORDS (superset of ANSWER_WORDS).
    guess_set = set(GUESS_WORDS)
    for word in result.words_tried:
        assert word in guess_set


def test_hail_mary_guesses_are_answer_candidates_only():
    # In hail mary mode every guess must be an answer candidate.
    result = solve_secret("serve", GUESS_WORDS, ANSWER_WORDS)
    answer_set = set(ANSWER_WORDS)
    for word, mode in zip(result.words_tried, result.mode_trace):
        if mode == "hail_mary":
            assert word in answer_set, f"{word!r} is not an answer-eligible word"


def test_solver_forces_hail_mary_by_investigate_limit():
    words = ["cigar", "rebut", "sissy", "humph", "awake", "blush", "focal", "evade", "naval", "serve"]
    answers = ["cigar", "awake", "blush", "focal", "evade", "naval", "serve"]
    config = SolverConfig(
        investigate_limit=3,
        threshold_known_letters=10,
        threshold_locked_positions=10,
        threshold_candidate_count=1,
    )
    result = solve_secret("serve", words, answers, config=config)
    if len(result.mode_trace) >= 4:
        assert result.mode_trace[3] == "hail_mary"
