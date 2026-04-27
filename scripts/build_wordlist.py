#!/usr/bin/env python3
"""Merge all word sources into a single 5-letter word list and clean up."""

import csv
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

FULL_DICT = DATA_DIR / "full-dict.txt"
FIVE_LETTER = DATA_DIR / "5-letter-words.txt"
DATASET_CSV = DATA_DIR / "wordle-test-dataset.csv"
OUT_FILE = DATA_DIR / "words.txt"


def collect_five_letter_words() -> set[str]:
    words: set[str] = set()

    # Primary source: full dictionary
    if FULL_DICT.exists():
        with FULL_DICT.open("r", encoding="utf-8", buffering=1 << 20) as fh:
            for line in fh:
                w = line.strip().lower()
                if len(w) == 5 and w.isalpha():
                    words.add(w)
        print(f"After full-dict.txt: {len(words):,} words")

    # Supplement: existing 5-letter word list
    added_from_five = 0
    if FIVE_LETTER.exists():
        with FIVE_LETTER.open("r", encoding="utf-8") as fh:
            for line in fh:
                w = line.strip().lower()
                if len(w) == 5 and w.isalpha() and w not in words:
                    words.add(w)
                    added_from_five += 1
        print(f"Added {added_from_five:,} extra words from 5-letter-words.txt")

    # Supplement: official answer CSV
    added_from_csv = 0
    if DATASET_CSV.exists():
        with DATASET_CSV.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                w = (row.get("word") or "").strip().lower()
                if len(w) == 5 and w.isalpha() and w not in words:
                    words.add(w)
                    added_from_csv += 1
        print(f"Added {added_from_csv:,} extra words from wordle-test-dataset.csv")

    return words


def write_wordlist(words: set[str]) -> None:
    sorted_words = sorted(words)
    with OUT_FILE.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(sorted_words) + "\n")
    print(f"Written {len(sorted_words):,} words to {OUT_FILE}")


def delete_old_files() -> None:
    for path in (FULL_DICT, FIVE_LETTER, DATASET_CSV):
        if path.exists():
            path.unlink()
            print(f"Deleted {path.name}")


if __name__ == "__main__":
    words = collect_five_letter_words()
    if not words:
        print("ERROR: no words collected — aborting", file=sys.stderr)
        sys.exit(1)
    write_wordlist(words)
    delete_old_files()
    print("Done.")
