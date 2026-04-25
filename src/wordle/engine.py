"""Wordle scoring engine."""

from collections import Counter


def score_guess(secret: str, guess: str) -> list[int]:
    """Return per-position score using Wordle semantics."""
    score = [0] * 5
    remaining = Counter()

    for idx, (s_char, g_char) in enumerate(zip(secret, guess)):
        if s_char == g_char:
            score[idx] = 2
        else:
            remaining[s_char] += 1

    for idx, g_char in enumerate(guess):
        if score[idx] == 0 and remaining[g_char] > 0:
            score[idx] = 1
            remaining[g_char] -= 1

    return score
