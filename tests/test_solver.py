from wordle.solver.strategy import SolverConfig, MODE_C_OPENER, solve_secret

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


# Mode C tests ──────────────────────────────────────────────────────────────

ANSWER_WORDS_C = ["crane", "crate", "slate", "solar", "plumb", "trove", "blunt", "feast"]
GUESS_WORDS_C = ANSWER_WORDS_C + ["rebut", "sissy", "humph", "audio", "soare", "clint"]


def test_mode_c_opens_with_fixed_opener():
    config = SolverConfig(mode="c")
    result = solve_secret("slate", GUESS_WORDS_C, ANSWER_WORDS_C, config=config)
    assert result.solved is True
    assert result.words_tried[0] == MODE_C_OPENER, (
        f"Mode C must open with {MODE_C_OPENER!r}, got {result.words_tried[0]!r}"
    )


def test_mode_c_solves_within_six_turns():
    config = SolverConfig(mode="c")
    for secret in ANSWER_WORDS_C:
        result = solve_secret(secret, GUESS_WORDS_C, ANSWER_WORDS_C, config=config)
        assert result.solved is True, f"Mode C failed to solve {secret!r}"
        assert result.turns_taken <= 6, f"Mode C used {result.turns_taken} turns for {secret!r}"


def test_mode_c_mode_trace_labels():
    config = SolverConfig(mode="c")
    result = solve_secret("solar", GUESS_WORDS_C, ANSWER_WORDS_C, config=config)
    assert result.solved is True
    valid_labels = {"entropy_opener", "entropy_lookup", "entropy_candidates", "direct"}
    for label in result.mode_trace:
        assert label in valid_labels, f"Unexpected mode trace label: {label!r}"
    assert result.mode_trace[0] == "entropy_opener"
