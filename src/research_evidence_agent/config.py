"""Environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    search_provider: str = "demo"
    answer_provider: str = "demo"
    search_max_results: int = 5
    research_paper_provider: str = "demo"
    academic_query_planner: str = "demo"
    research_max_results_per_query: int = 5
    arxiv_api_url: str = "https://export.arxiv.org/api/query"
    arxiv_min_interval_seconds: float = 3.0
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    database_url: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            search_provider=os.getenv("SEARCH_PROVIDER", "demo").strip().lower(),
            answer_provider=os.getenv("ANSWER_PROVIDER", "demo").strip().lower(),
            search_max_results=_bounded_int(
                os.getenv("SEARCH_MAX_RESULTS", "5"), minimum=1, maximum=10
            ),
            research_paper_provider=os.getenv(
                "RESEARCH_PAPER_PROVIDER", "demo"
            ).strip().lower(),
            academic_query_planner=os.getenv(
                "ACADEMIC_QUERY_PLANNER", "demo"
            ).strip().lower(),
            research_max_results_per_query=_bounded_int(
                os.getenv("RESEARCH_MAX_RESULTS_PER_QUERY", "5"),
                minimum=1,
                maximum=20,
            ),
            arxiv_api_url=os.getenv(
                "ARXIV_API_URL", "https://export.arxiv.org/api/query"
            ).strip(),
            arxiv_min_interval_seconds=_bounded_float(
                os.getenv("ARXIV_MIN_INTERVAL_SECONDS", "3"),
                minimum=0.0,
                maximum=30.0,
            ),
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_base_url=os.getenv(
                "LLM_BASE_URL", "https://api.openai.com/v1"
            ).strip(),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
            database_url=os.getenv("DATABASE_URL", "").strip(),
        )


def _bounded_int(raw_value: str, *, minimum: int, maximum: int) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Expected an integer, got {raw_value!r}") from exc
    return max(minimum, min(value, maximum))


def _bounded_float(raw_value: str, *, minimum: float, maximum: float) -> float:
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"Expected a number, got {raw_value!r}") from exc
    return max(minimum, min(value, maximum))
