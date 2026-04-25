"""Async batch runner for solver evaluation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from wordle.batch.metrics import PuzzleResult, serialize_results, summarize_results
from wordle.constants import REPORTS_DIR
from wordle.data import WordleData
from wordle.solver.strategy import SolverConfig, solve_secret


async def run_batch(
    data: WordleData,
    *,
    concurrency: int = 16,
    limit: int | None = None,
    reports_dir: Path = REPORTS_DIR,
    config: SolverConfig | None = None,
) -> tuple[list[PuzzleResult], dict]:
    answers = list(data.official_answers)
    if limit is not None:
        answers = answers[:limit]

    semaphore = asyncio.Semaphore(concurrency)
    guess_words = list(data.guess_words)

    async def worker(secret: str) -> PuzzleResult:
        async with semaphore:
            result = solve_secret(secret, guess_words, answers, config=config)
            return PuzzleResult(
                secret=secret,
                solved=result.solved,
                turns_taken=result.turns_taken,
                words_tried=result.words_tried,
                mode_trace=result.mode_trace,
            )

    tasks = [asyncio.create_task(worker(secret)) for secret in answers]
    results: list[PuzzleResult] = []

    try:
        for completed in asyncio.as_completed(tasks):
            results.append(await completed)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        raise

    summary = summarize_results(results)
    reports_dir.mkdir(parents=True, exist_ok=True)

    with (reports_dir / "results.json").open("w", encoding="utf-8") as file:
        json.dump(serialize_results(results), file, indent=2)

    with (reports_dir / "summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    return results, summary
