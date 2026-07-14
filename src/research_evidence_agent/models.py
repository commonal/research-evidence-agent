"""Public API request and response models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class ResearchPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=2_000)
    thread_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("question must contain at least 3 non-whitespace characters")
        return normalized


class ResearchSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str | None = Field(default=None, min_length=1, max_length=64)
    question: str | None = Field(default=None, min_length=3, max_length=2_000)

    @model_validator(mode="after")
    def require_exactly_one_selection(self):
        if bool(self.option_id) == bool(self.question):
            raise ValueError("provide exactly one of option_id or question")
        if self.question:
            self.question = " ".join(self.question.split())
        return self


class SubQuestionResponse(BaseModel):
    id: str
    question: str
    scope: str


class ResearchTraceResponse(BaseModel):
    node: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class AcademicSearchPlanResponse(BaseModel):
    queries: list[str]
    keywords: list[str]


class LLMUsageCallResponse(BaseModel):
    operation: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    reasoning_tokens: int = 0


class LLMUsageSummaryResponse(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    reasoning_tokens: int = 0
    calls: list[LLMUsageCallResponse] = Field(default_factory=list)


class PaperResponse(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published_at: datetime
    updated_at: datetime
    categories: list[str]
    abs_url: str
    pdf_url: str
    matched_queries: list[str]
    rank: int


class ResearchPlanResponse(BaseModel):
    request_id: str
    thread_id: str
    status: Literal[
        "analyzing",
        "awaiting_selection",
        "ready",
        "searching",
        "papers_ready",
        "no_results",
    ]
    original_question: str
    selected_question: str | None
    subquestions: list[SubQuestionResponse]
    search_plan: AcademicSearchPlanResponse | None = None
    usage: LLMUsageSummaryResponse = Field(default_factory=LLMUsageSummaryResponse)
    papers: list[PaperResponse] = Field(default_factory=list)
    search_errors: list[str] = Field(default_factory=list)
    trace: list[ResearchTraceResponse]
