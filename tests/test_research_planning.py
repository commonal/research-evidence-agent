from __future__ import annotations

import asyncio

import pytest

from agentic_search_demo.models import ResearchPlanRequest, ResearchSelectionRequest
from agentic_search_demo.research.nodes import ResearchDependencies
from agentic_search_demo.research.planner import DemoQuestionPlanner
from agentic_search_demo.research.service import (
    ResearchPlanningService,
    ResearchThreadNotFound,
)


def make_service() -> ResearchPlanningService:
    return ResearchPlanningService(
        ResearchDependencies(question_planner=DemoQuestionPlanner())
    )


def test_focused_question_is_ready_without_interrupt() -> None:
    result = asyncio.run(
        make_service().plan(
            ResearchPlanRequest(
                question="长上下文模型能否在多跳问答任务中替代 RAG？"
            )
        )
    )

    assert result.status == "ready"
    assert result.selected_question == result.original_question
    assert result.subquestions == []
    assert [event.node for event in result.trace] == [
        "analyze_question",
        "finalize_question",
    ]


def test_broad_question_pauses_and_resumes_with_option() -> None:
    async def scenario():
        service = make_service()
        planned = await service.plan(ResearchPlanRequest(question="大模型记忆"))
        resumed = await service.select(
            planned.thread_id,
            ResearchSelectionRequest(option_id=planned.subquestions[1].id),
        )
        return planned, resumed

    planned, resumed = asyncio.run(scenario())
    assert planned.status == "awaiting_selection"
    assert len(planned.subquestions) == 4
    assert planned.selected_question is None
    assert resumed.status == "ready"
    assert resumed.selected_question == planned.subquestions[1].question
    assert "wait_for_user_selection" in [event.node for event in resumed.trace]


def test_broad_question_accepts_user_edited_question() -> None:
    async def scenario():
        service = make_service()
        planned = await service.plan(ResearchPlanRequest(question="智能体记忆"))
        return await service.select(
            planned.thread_id,
            ResearchSelectionRequest(
                question="长期对话中向量记忆压缩是否会损失关键事实？"
            ),
        )

    resumed = asyncio.run(scenario())
    assert resumed.status == "ready"
    assert resumed.selected_question == "长期对话中向量记忆压缩是否会损失关键事实？"


def test_unknown_thread_is_rejected() -> None:
    with pytest.raises(ResearchThreadNotFound):
        asyncio.run(
            make_service().select(
                "missing-thread", ResearchSelectionRequest(option_id="sq_1")
            )
        )
