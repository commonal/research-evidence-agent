from __future__ import annotations

from typing import Any, Literal, TypedDict


ResearchStatus = Literal["analyzing", "awaiting_selection", "ready"]


class SubQuestion(TypedDict):
    id: str
    question: str
    scope: str


class ResearchTraceEvent(TypedDict):
    node: str
    message: str
    details: dict[str, Any]


class ResearchState(TypedDict, total=False):
    request_id: str
    thread_id: str
    original_question: str
    selected_question: str
    is_broad: bool
    status: ResearchStatus
    subquestions: list[SubQuestion]
    trace: list[ResearchTraceEvent]
