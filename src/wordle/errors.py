"""Domain errors."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WordleRuleError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
