"""Shared constants."""

import os
from pathlib import Path

MAX_TURNS = 6
WORD_LENGTH = 5

ROOT_DIR = Path(os.environ.get("WORDLE_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT_DIR / "data"
DEFAULT_WORDS_PATH = DATA_DIR / "words.txt"
DEFAULT_GUESSES_PATH = DATA_DIR / "allowed-guesses.txt"
REPORTS_DIR = ROOT_DIR / "reports"
REPORTS_MODE_A_DIR = REPORTS_DIR / "mode-a"
REPORTS_MODE_B_DIR = REPORTS_DIR / "mode-b"
