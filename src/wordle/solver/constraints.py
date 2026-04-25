"""Constraint extraction and candidate filtering."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class SolverConstraints:
    fixed_positions: dict[int, str] = field(default_factory=dict)
    excluded_positions: dict[int, set[str]] = field(default_factory=lambda: defaultdict(set))
    min_counts: dict[str, int] = field(default_factory=dict)
    max_counts: dict[str, int] = field(default_factory=dict)

    def update(self, guess: str, score: list[int]) -> None:
        positives = Counter()
        totals = Counter(guess)

        for idx, (char, value) in enumerate(zip(guess, score)):
            if value == 2:
                self.fixed_positions[idx] = char
                positives[char] += 1
            elif value == 1:
                self.excluded_positions[idx].add(char)
                positives[char] += 1
            else:
                self.excluded_positions[idx].add(char)

        for char, count in positives.items():
            self.min_counts[char] = max(self.min_counts.get(char, 0), count)

        for char, total in totals.items():
            positive_count = positives.get(char, 0)
            if positive_count < total:
                self.max_counts[char] = min(self.max_counts.get(char, 5), positive_count)
            elif char not in self.max_counts:
                self.max_counts[char] = max(self.max_counts.get(char, 5), positive_count)

    def candidate_matches(self, word: str) -> bool:
        counts = Counter(word)

        for idx, char in self.fixed_positions.items():
            if word[idx] != char:
                return False

        for idx, blocked in self.excluded_positions.items():
            if word[idx] in blocked and self.fixed_positions.get(idx) != word[idx]:
                return False

        for char, minimum in self.min_counts.items():
            if counts[char] < minimum:
                return False

        for char, maximum in self.max_counts.items():
            if counts[char] > maximum:
                return False

        return True
