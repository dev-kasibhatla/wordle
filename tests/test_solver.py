from wordle.solver.strategy import SolverConfig, solve_secret


def test_solver_solves_secret_within_six_turns():
    words = ["cigar", "rebut", "sissy", "humph", "awake", "blush", "focal", "evade", "naval", "serve"]
    result = solve_secret("cigar", words, words)
    assert result.solved is True
    assert 1 <= result.turns_taken <= 6


def test_solver_forces_hail_mary_by_turn_four():
    words = ["cigar", "rebut", "sissy", "humph", "awake", "blush", "focal", "evade", "naval", "serve"]
    config = SolverConfig(
        investigate_limit=3,
        threshold_known_letters=10,
        threshold_locked_positions=10,
        threshold_candidate_count=1,
    )
    result = solve_secret("serve", words, words, config=config)
    if len(result.mode_trace) >= 4:
        assert result.mode_trace[3] == "hail_mary"
