"""Batch solver evaluator."""

from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from wordle.batch.metrics import PuzzleResult, serialize_results, summarize_results
from wordle.batch.report import generate_markdown_report
from wordle.constants import REPORTS_DIR
from wordle.data import WordleData
from wordle.solver.strategy import SolverConfig, solve_secret


def _solve_worker(args: tuple[str, list[str], list[str], SolverConfig | None]) -> PuzzleResult:
    """Top-level function required for ProcessPoolExecutor pickling."""
    secret, guess_words, answer_words, config = args
    result = solve_secret(secret, guess_words, answer_words, config=config)
    return PuzzleResult(
        secret=secret,
        solved=result.solved,
        turns_taken=result.turns_taken,
        words_tried=result.words_tried,
        mode_trace=result.mode_trace,
    )


async def run_batch(
    data: WordleData,
    *,
    concurrency: int | None = None,
    limit: int | None = None,
    reports_dir: Path = REPORTS_DIR,
    config: SolverConfig | None = None,
) -> tuple[list[PuzzleResult], dict]:
    answers = list(data.official_answers)
    if limit is not None:
        answers = answers[:limit]

    guess_words = list(data.guess_words)
    workers = concurrency or os.cpu_count() or 4
    loop = asyncio.get_running_loop()
    args_list = [(secret, guess_words, answers, config) for secret in answers]

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [loop.run_in_executor(pool, _solve_worker, args) for args in args_list]
        results: list[PuzzleResult] = list(await asyncio.gather(*futures))

    summary = summarize_results(results)
    reports_dir.mkdir(parents=True, exist_ok=True)

    with (reports_dir / "results.json").open("w", encoding="utf-8") as file:
        json.dump(serialize_results(results), file, indent=2)

    with (reports_dir / "summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    mode = (config.mode if config else None) or "a"
    generate_markdown_report(results, summary, reports_dir, mode=mode)

    return results, summary
