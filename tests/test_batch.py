import asyncio
from pathlib import Path

from wordle.batch.runner import run_batch
from wordle.data import WordleData


def test_batch_creates_reports(tmp_path: Path):
    guesses = ("cigar", "rebut", "sissy", "humph", "awake", "serve")
    answers = ("cigar", "awake", "serve")
    data = WordleData(guess_words=guesses, official_answers=answers)

    results, summary = asyncio.run(run_batch(data, concurrency=2, reports_dir=tmp_path))

    assert len(results) == 3
    assert summary["total_puzzles"] == 3
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "graphs" / "turns_histogram.png").exists()
    assert (tmp_path / "graphs" / "solve_rate.png").exists()
