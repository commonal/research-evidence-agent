from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchMode(StrEnum):
    AUTO = "auto"
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=2_000)
    mode: SearchMode = SearchMode.AUTO
    max_iterations: int = Field(default=2, ge=1, le=4)
    thread_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3:
            raise ValueError("query must contain at least 3 non-whitespace characters")
        return value


class CitationResponse(BaseModel):
    index: int
    source_id: str
    title: str
    url: str
    quote: str


class SourceResponse(BaseModel):
    id: str
    title: str
    url: str
    content: str
    score: float
    source_type: str
    query: str


class TraceResponse(BaseModel):
    node: str
    message: str
    search_round: int
    details: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    request_id: str
    thread_id: str
    query: str
    mode: SearchMode
    answer: str
    citations: list[CitationResponse]
    invalid_citation_count: int = 0
    sources: list[SourceResponse]
    evidence_score: float
    evidence_sufficient: bool
    search_rounds: int
    trace: list[TraceResponse]


class HealthResponse(BaseModel):
    status: str
    graph: str
    search_provider: str
    answer_provider: str
