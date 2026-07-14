from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    search_provider: str = "demo"
    answer_provider: str = "demo"
    search_max_results: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            search_provider=os.getenv("SEARCH_PROVIDER", "demo").strip().lower(),
            answer_provider=os.getenv("ANSWER_PROVIDER", "demo").strip().lower(),
            search_max_results=_bounded_int(
                os.getenv("SEARCH_MAX_RESULTS", "5"), minimum=1, maximum=10
            ),
        )


def _bounded_int(raw_value: str, *, minimum: int, maximum: int) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Expected an integer, got {raw_value!r}") from exc
    return max(minimum, min(value, maximum))

