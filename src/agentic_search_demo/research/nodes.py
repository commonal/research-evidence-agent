from __future__ import annotations

from dataclasses import dataclass

from langgraph.types import interrupt

from agentic_search_demo.research.planner import QuestionPlanner
from agentic_search_demo.research.state import (
    ResearchState,
    ResearchTraceEvent,
    SubQuestion,
)


class InvalidResearchSelection(ValueError):
    """Raised when a resume payload does not identify a valid question."""


@dataclass(frozen=True, slots=True)
class ResearchDependencies:
    question_planner: QuestionPlanner


def _trace(node: str, message: str, **details) -> ResearchTraceEvent:
    return ResearchTraceEvent(node=node, message=message, details=details)


def _append_trace(
    state: ResearchState, event: ResearchTraceEvent
) -> list[ResearchTraceEvent]:
    return [*state.get("trace", []), event]


async def analyze_question(
    state: ResearchState, deps: ResearchDependencies
) -> dict:
    question = state["original_question"]
    is_broad = await deps.question_planner.is_broad(question)
    message = "问题范围较宽，需要用户选择具体研究问题" if is_broad else "问题范围明确，可以进入研究"
    return {
        "is_broad": is_broad,
        "status": "analyzing",
        "trace": _append_trace(
            state,
            _trace(
                "analyze_question",
                message,
                is_broad=is_broad,
                planner=deps.question_planner.name,
            ),
        ),
    }


async def generate_subquestions(
    state: ResearchState, deps: ResearchDependencies
) -> dict:
    questions = await deps.question_planner.decompose(state["original_question"])
    if not 3 <= len(questions) <= 5:
        raise ValueError("question planner must return between 3 and 5 subquestions")
    return {
        "subquestions": questions,
        "status": "awaiting_selection",
        "trace": _append_trace(
            state,
            _trace(
                "generate_subquestions",
                f"已生成 {len(questions)} 个候选研究问题",
                subquestion_count=len(questions),
            ),
        ),
    }


def wait_for_user_selection(state: ResearchState) -> dict:
    selection = interrupt(
        {
            "kind": "research_question_selection",
            "original_question": state["original_question"],
            "subquestions": state.get("subquestions", []),
        }
    )
    selected = _resolve_selection(state.get("subquestions", []), selection)
    return {
        "selected_question": selected,
        "status": "ready",
        "trace": _append_trace(
            state,
            _trace(
                "wait_for_user_selection",
                "用户已确认具体研究问题",
                selected_question=selected,
            ),
        ),
    }


def finalize_question(state: ResearchState) -> dict:
    selected = state.get("selected_question") or state["original_question"]
    return {
        "selected_question": selected,
        "status": "ready",
        "trace": _append_trace(
            state,
            _trace(
                "finalize_question",
                "研究问题已就绪，下一阶段将进入 Arxiv 检索",
                selected_question=selected,
            ),
        ),
    }


def route_after_analysis(state: ResearchState) -> str:
    return "decompose" if state.get("is_broad") else "finalize"


def _resolve_selection(
    subquestions: list[SubQuestion], selection: object
) -> str:
    if not isinstance(selection, dict):
        raise InvalidResearchSelection("selection payload must be an object")

    custom_question = " ".join(str(selection.get("question") or "").split())
    if custom_question:
        if len(custom_question) < 3:
            raise InvalidResearchSelection("custom question is too short")
        return custom_question

    option_id = str(selection.get("option_id") or "")
    for option in subquestions:
        if option["id"] == option_id:
            return option["question"]
    raise InvalidResearchSelection("option_id does not match a candidate question")
