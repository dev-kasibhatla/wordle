"""CLI entrypoints."""

from __future__ import annotations

import argparse
import asyncio
import json

import uvicorn

from wordle.api.app import create_app
from wordle.batch.runner import run_batch
from wordle.constants import REPORTS_MODE_A_DIR, REPORTS_MODE_B_DIR, REPORTS_MODE_C_DIR
from wordle.data import find_missing_answers, load_wordle_data
from wordle.solver.strategy import SolverConfig


def run_api() -> None:
    """Run FastAPI app."""
    uvicorn.run("wordle.api.app:create_app", factory=True, host="0.0.0.0", port=8000)


def run_batch_cmd() -> None:
    """Run solver batch evaluator."""
    parser = argparse.ArgumentParser(description="Run Wordle solver batch")
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--mode",
        choices=["a", "b", "c"],
        default="a",
        help="a=investigation+hail-mary, b=hail-mary only, c=entropy-optimal",
    )
    args = parser.parse_args()

    data = load_wordle_data()
    config = SolverConfig(mode=args.mode)
    reports_dir = {
        "a": REPORTS_MODE_A_DIR,
        "b": REPORTS_MODE_B_DIR,
        "c": REPORTS_MODE_C_DIR,
    }[args.mode]

    _, summary = asyncio.run(_run_batch_async(data, args.concurrency, args.limit, config, reports_dir))
    print(json.dumps(summary, indent=2))


async def _run_batch_async(data, concurrency, limit, config, reports_dir):
    from pathlib import Path
    return await run_batch(data, concurrency=concurrency, limit=limit, config=config, reports_dir=Path(reports_dir))


def run_consistency_check() -> None:
    """Verify answers exist in dictionary."""
    data = load_wordle_data()
    missing = find_missing_answers(data)
    if missing:
        print(json.dumps({"missing": missing}, indent=2))
        raise SystemExit(1)
    print(json.dumps({"missing": []}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Wordle utility entrypoint")
    parser.add_argument("command", choices=["api", "batch", "check-dataset"])
    args = parser.parse_args()

    if args.command == "api":
        run_api()
    elif args.command == "batch":
        run_batch_cmd()
    else:
        run_consistency_check()


if __name__ == "__main__":
    main()
