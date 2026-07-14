"""State types for academic research planning and paper discovery."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


ResearchStatus = Literal[
    "analyzing",
    "awaiting_selection",
    "ready",
    "searching",
    "papers_ready",
    "no_results",
]


class SubQuestion(TypedDict):
    id: str
    question: str
    scope: str


class ResearchTraceEvent(TypedDict):
    node: str
    message: str
    details: dict[str, Any]


class AcademicSearchPlan(TypedDict):
    queries: list[str]
    keywords: list[str]


class Paper(TypedDict):
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published_at: str
    updated_at: str
    categories: list[str]
    abs_url: str
    pdf_url: str
    matched_queries: list[str]
    rank: int


class ResearchState(TypedDict, total=False):
    request_id: str
    thread_id: str
    original_question: str
    selected_question: str
    is_broad: bool
    status: ResearchStatus
    subquestions: list[SubQuestion]
    search_plan: AcademicSearchPlan
    papers: list[Paper]
    search_errors: list[str]
    trace: list[ResearchTraceEvent]
