"""CLI entrypoints for API, batch runner, and consistency checks."""

from __future__ import annotations

import argparse
import asyncio
import json

import uvicorn

from wordle.api.app import create_app
from wordle.batch.runner import run_batch as run_batch_eval
from wordle.data import find_missing_answers, load_wordle_data


def run_api() -> None:
    """Run FastAPI app."""
    uvicorn.run("wordle.api.app:create_app", factory=True, host="0.0.0.0", port=8000)


def run_batch() -> None:
    """Run solver batch evaluator."""
    parser = argparse.ArgumentParser(description="Run Wordle solver batch")
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    data = load_wordle_data()
    _, summary = asyncio.run(run_batch_async(data, args.concurrency, args.limit))
    print(json.dumps(summary, indent=2))


async def run_batch_async(data, concurrency: int, limit: int | None):
    return await run_batch_eval(data, concurrency=concurrency, limit=limit)


def run_consistency_check() -> None:
    """Verify official answers are all present in dictionary."""
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
        run_batch()
    else:
        run_consistency_check()


if __name__ == "__main__":
    main()
