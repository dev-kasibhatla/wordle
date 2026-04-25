"""Full batch run using mode B (hail mary from turn 1). Marked slow."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from wordle.batch.runner import run_batch
from wordle.constants import REPORTS_MODE_B_DIR
from wordle.data import load_wordle_data
from wordle.solver.strategy import SolverConfig


@pytest.mark.slow
def test_hail_mary_full_batch_solve_rate():
    """Run all official Wordle puzzles with mode B and write mode-b reports."""
    data = load_wordle_data()
    config = SolverConfig(mode="b")

    results, summary = asyncio.run(
        run_batch(data, concurrency=16, config=config, reports_dir=REPORTS_MODE_B_DIR)
    )

    assert summary["total_puzzles"] == len(data.official_answers)
    assert summary["solve_rate"] >= 0.90, (
        f"mode B solve rate {summary['solve_rate']:.1%} fell below 90%"
    )
    assert (REPORTS_MODE_B_DIR / "results.json").exists()
    assert (REPORTS_MODE_B_DIR / "summary.json").exists()
    assert (REPORTS_MODE_B_DIR / "report.md").exists()
    assert (REPORTS_MODE_B_DIR / "graphs" / "turns_histogram.png").exists()
    assert (REPORTS_MODE_B_DIR / "graphs" / "solve_rate.png").exists()


@pytest.mark.slow
def test_hail_mary_mode_trace_always_hail_mary():
    """Every turn in mode B must be hail_mary."""
    data = load_wordle_data()
    config = SolverConfig(mode="b")

    results, _ = asyncio.run(
        run_batch(data, concurrency=16, config=config, reports_dir=REPORTS_MODE_B_DIR)
    )

    for result in results:
        for turn_mode in result.mode_trace:
            assert turn_mode == "hail_mary", (
                f"{result.secret}: expected all turns hail_mary, got {result.mode_trace}"
            )
