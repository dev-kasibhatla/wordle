"""Batch metrics aggregation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import statistics


@dataclass(frozen=True)
class PuzzleResult:
    secret: str
    solved: bool
    turns_taken: int
    words_tried: list[str]
    mode_trace: list[str]


def summarize_results(results: list[PuzzleResult]) -> dict:
    total = len(results)
    solved_results = [item for item in results if item.solved]
    failed_results = [item for item in results if not item.solved]

    solved_turns = [item.turns_taken for item in solved_results]
    histogram = {str(turn): 0 for turn in range(1, 7)}
    for turns in solved_turns:
        histogram[str(turns)] = histogram.get(str(turns), 0) + 1

    mode_turn4_hail_mary = sum(1 for item in results if len(item.mode_trace) >= 4 and item.mode_trace[3] == "hail_mary")

    summary = {
        "total_puzzles": total,
        "solved": len(solved_results),
        "failed": len(failed_results),
        "solve_rate": (len(solved_results) / total) if total else 0.0,
        "turns_histogram": histogram,
        "forced_hail_mary_turn4_count": mode_turn4_hail_mary,
        "average_turns_solved": statistics.fmean(solved_turns) if solved_turns else 0.0,
        "median_turns_solved": statistics.median(solved_turns) if solved_turns else 0.0,
        "p90_turns_solved": _percentile(solved_turns, 90),
        "top_failures": [
            {
                "secret": item.secret,
                "words_tried": item.words_tried,
            }
            for item in failed_results[:10]
        ],
    }
    return summary


def serialize_results(results: list[PuzzleResult]) -> list[dict]:
    return [asdict(item) for item in results]


def _percentile(values: list[int], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * (percentile / 100)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
