"""Shared constants."""

from pathlib import Path

MAX_TURNS = 6
WORD_LENGTH = 5

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DEFAULT_GUESS_PATH = DATA_DIR / "5-letter-words.txt"
DEFAULT_DATASET_PATH = DATA_DIR / "wordle-test-dataset.csv"
REPORTS_DIR = ROOT_DIR / "reports"
