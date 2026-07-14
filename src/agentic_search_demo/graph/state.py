from __future__ import annotations

from typing import Any, Literal, TypedDict


SearchModeValue = Literal["auto", "quick", "standard", "deep"]


class Source(TypedDict):
    id: str
    title: str
    url: str
    content: str
    score: float
    source_type: str
    query: str


class Citation(TypedDict):
    index: int
    source_id: str
    title: str
    url: str
    quote: str


class TraceEvent(TypedDict):
    node: str
    message: str
    search_round: int
    details: dict[str, Any]


class AnswerDraft(TypedDict):
    answer: str
    citations: list[Citation]


class SearchState(TypedDict, total=False):
    request_id: str
    thread_id: str
    query: str
    requested_mode: SearchModeValue
    mode: SearchModeValue
    max_iterations: int
    search_round: int
    sub_queries: list[str]
    searched_queries: list[str]
    sources: list[Source]
    missing_topics: list[str]
    evidence_score: float
    evidence_sufficient: bool
    answer: str
    citations: list[Citation]
    invalid_citation_count: int
    verification_passed: bool
    trace: list[TraceEvent]
