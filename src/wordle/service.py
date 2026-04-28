"""Game manager."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4
import random

from wordle.data import WordleData, choose_random_answer
from wordle.errors import WordleRuleError
from wordle.game import GameState, GuessFeedback, WordleGameEngine
from wordle.solver.constraints import SolverConstraints
from wordle.solver.strategy import (
    SolverConfig,
    MODE_C_OPENER,
    MODE_C_TURN2,
    MODE_C_TURN3,
    _build_letter_frequencies,
    _best_entropy_guess,
    _select_hail_mary_guess,
    _select_investigate_guess,
    _select_separator_guess,
    _should_use_hail_mary,
    solve_secret,
)


@dataclass(frozen=True)
class PlayResult:
    game_id: str
    state: GameState
    latest: tuple[str, list[int]] | None


@dataclass(frozen=True)
class SolverTurnResult:
    turn: int
    guess: str
    score: list[int]
    mode: str
    candidates_remaining: int


@dataclass(frozen=True)
class SolverResult:
    solved: bool
    turns_taken: int
    turns: list[SolverTurnResult]


class GameManager:
    """Game registry."""

    def __init__(self, data: WordleData, seed: int | None = None) -> None:
        self.data = data
        self.engine = WordleGameEngine(data.guess_word_set)
        self._games: dict[str, GameState] = {}
        self._rng = random.Random(seed)

    def new_game(self) -> PlayResult:
        secret = choose_random_answer(self.data, self._rng)
        game_id = str(uuid4())
        state = GameState(secret=secret)
        self._games[game_id] = state
        return PlayResult(game_id=game_id, state=state, latest=None)

    def get_game(self, game_id: str) -> GameState:
        state = self._games.get(game_id)
        if state is None:
            raise WordleRuleError("unknown_game", "game_id not found")
        return state

    def play_guess(self, game_id: str, guess: str) -> PlayResult:
        state = self._games.get(game_id)
        if state is None:
            raise WordleRuleError("unknown_game", "game_id not found")
        feedback = self.engine.apply_guess(state, guess)
        return PlayResult(
            game_id=game_id,
            state=state,
            latest=(feedback.guess, feedback.score),
        )

    def run_solver(self, secret: str, config: SolverConfig) -> SolverResult:
        """Run the solver from a blank board for the given secret."""
        from wordle.engine import score_guess
        from wordle.constants import MAX_TURNS

        if secret not in set(self.data.official_answers):
            # allow any valid guess word too
            if secret not in set(self.data.guess_words):
                raise WordleRuleError("unknown_word", "secret is not in dictionary")

        guess_words = list(self.data.guess_words)
        answer_words = list(self.data.official_answers)

        # Mode C is fully self-contained in strategy.solve_secret.
        if config.mode == "c":
            result = solve_secret(secret, guess_words, answer_words, config=config)
            turns = [
                SolverTurnResult(
                    turn=i + 1,
                    guess=g,
                    score=score_guess(secret, g),
                    mode=m,
                    candidates_remaining=0,  # not tracked in mode C path
                )
                for i, (g, m) in enumerate(zip(result.words_tried, result.mode_trace))
            ]
            return SolverResult(solved=result.solved, turns_taken=result.turns_taken, turns=turns)

        constraints = SolverConstraints()
        tried: set[str] = set()
        turns: list[SolverTurnResult] = []

        for turn_idx in range(MAX_TURNS):
            candidates = [w for w in answer_words if constraints.candidate_matches(w)]
            if not candidates:
                break
            use_hail_mary = _should_use_hail_mary(turn_idx, constraints, len(candidates), config)
            mode = "hail_mary" if use_hail_mary else "investigate"
            if use_hail_mary:
                if config.mode == "a" and len(candidates) > config.threshold_separator:
                    guess = _select_separator_guess(guess_words, candidates, tried)
                else:
                    guess = _select_hail_mary_guess(candidates, tried)
            else:
                guess = _select_investigate_guess(guess_words, tried, candidates, constraints)
            tried.add(guess)
            score = score_guess(secret, guess)
            turns.append(SolverTurnResult(
                turn=turn_idx + 1,
                guess=guess,
                score=score,
                mode=mode,
                candidates_remaining=len(candidates),
            ))
            if all(v == 2 for v in score):
                return SolverResult(solved=True, turns_taken=len(turns), turns=turns)
            constraints.update(guess, score)

        return SolverResult(solved=False, turns_taken=len(turns), turns=turns)

    def analyze_state(
        self,
        history: list[tuple[str, list[int]]],
        config: SolverConfig,
        secret: str | None = None,
    ) -> tuple[int, str | None, str | None, SolverResult | None]:
        """Return (candidates_remaining, suggestion, suggestion_mode, auto_finish)."""
        from wordle.engine import score_guess
        from wordle.constants import MAX_TURNS

        constraints = SolverConstraints()
        tried: set[str] = set()
        guess_words = list(self.data.guess_words)
        answer_words = list(self.data.official_answers)

        for guess, score in history:
            tried.add(guess)
            constraints.update(guess, score)

        candidates = [w for w in answer_words if constraints.candidate_matches(w)]
        turn_idx = len(history)

        suggestion: str | None = None
        suggestion_mode: str | None = None
        if candidates and turn_idx < MAX_TURNS:
            if config.mode == "c":
                if turn_idx == 0:
                    suggestion = MODE_C_OPENER
                    suggestion_mode = "entropy_opener"
                elif turn_idx == 1:
                    # Reconstruct opener pattern from history[0]
                    opener_score = history[0][1]
                    op_pat = opener_score[0] + 3 * opener_score[1] + 9 * opener_score[2] + 27 * opener_score[3] + 81 * opener_score[4]
                    suggestion = MODE_C_TURN2.get(op_pat, candidates[0])
                    if suggestion in tried:
                        suggestion = _best_entropy_guess(candidates, tried)
                    suggestion_mode = "entropy_lookup"
                elif turn_idx == 2:
                    if len(candidates) == 1:
                        suggestion = candidates[0]
                        suggestion_mode = "direct"
                    else:
                        opener_score = history[0][1]
                        op_pat = opener_score[0] + 3 * opener_score[1] + 9 * opener_score[2] + 27 * opener_score[3] + 81 * opener_score[4]
                        t2_score = history[1][1]
                        t2_pat = t2_score[0] + 3 * t2_score[1] + 9 * t2_score[2] + 27 * t2_score[3] + 81 * t2_score[4]
                        suggestion = MODE_C_TURN3.get((op_pat, t2_pat), "")
                        if not suggestion or suggestion in tried:
                            pool = guess_words if len(candidates) > config.threshold_full_pool else None
                            suggestion = _best_entropy_guess(candidates, tried, pool=pool)
                        suggestion_mode = "entropy_lookup"
                elif len(candidates) <= config.threshold_direct:
                    suggestion = next((w for w in candidates if w not in tried), candidates[0])
                    suggestion_mode = "direct"
                else:
                    pool = guess_words if len(candidates) > config.threshold_full_pool else None
                    suggestion = _best_entropy_guess(candidates, tried, pool=pool)
                    suggestion_mode = "entropy_candidates"
            else:
                use_hail_mary = _should_use_hail_mary(turn_idx, constraints, len(candidates), config)
                suggestion_mode = "hail_mary" if use_hail_mary else "investigate"
                if use_hail_mary:
                    if config.mode == "a" and len(candidates) > config.threshold_separator:
                        suggestion = _select_separator_guess(guess_words, candidates, tried)
                    else:
                        suggestion = _select_hail_mary_guess(candidates, tried)
                else:
                    suggestion = _select_investigate_guess(guess_words, tried, candidates, constraints)

        auto_finish: SolverResult | None = None
        if secret is not None and candidates and turn_idx < MAX_TURNS:
            if config.mode == "c":
                # Delegate mode C auto-finish to the centralised solver.
                result = solve_secret(secret, guess_words, answer_words, config=config)
                from wordle.engine import score_guess as _sg
                finish_turns = [
                    SolverTurnResult(turn=i + 1, guess=g, score=_sg(secret, g), mode=m, candidates_remaining=0)
                    for i, (g, m) in enumerate(zip(result.words_tried[turn_idx:], result.mode_trace[turn_idx:]))
                ]
                auto_finish = SolverResult(solved=result.solved, turns_taken=result.turns_taken, turns=finish_turns)
            else:
                # replay from current state to finish
                c2 = SolverConstraints()
                t2: set[str] = set()
                for g, s in history:
                    t2.add(g)
                    c2.update(g, s)
                finish_turns = []
                for i in range(turn_idx, MAX_TURNS):
                    cands = [w for w in answer_words if c2.candidate_matches(w)]
                    if not cands:
                        break
                    uhm = _should_use_hail_mary(i, c2, len(cands), config)
                    m = "hail_mary" if uhm else "investigate"
                    if uhm:
                        if config.mode == "a" and len(cands) > config.threshold_separator:
                            g = _select_separator_guess(guess_words, cands, t2)
                        else:
                            g = _select_hail_mary_guess(cands, t2)
                    else:
                        g = _select_investigate_guess(guess_words, t2, cands, c2)
                    t2.add(g)
                    sc = score_guess(secret, g)
                    finish_turns.append(SolverTurnResult(turn=i + 1, guess=g, score=sc, mode=m, candidates_remaining=len(cands)))
                    if all(v == 2 for v in sc):
                        break
                    c2.update(g, sc)
                solved = bool(finish_turns) and all(v == 2 for v in finish_turns[-1].score)
                auto_finish = SolverResult(solved=solved, turns_taken=len(history) + len(finish_turns), turns=finish_turns)

        return len(candidates), suggestion, suggestion_mode, auto_finish