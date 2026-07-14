from __future__ import annotations

import asyncio

import pytest

from research_evidence_agent.models import ResearchPlanRequest, ResearchSelectionRequest
from research_evidence_agent.research.academic import (
    DemoAcademicQueryPlanner,
    DemoPaperProvider,
)
from research_evidence_agent.research.nodes import ResearchDependencies
from research_evidence_agent.research.planner import DemoQuestionPlanner
from research_evidence_agent.research.service import (
    ResearchPlanningService,
    ResearchThreadNotFound,
)


def make_service() -> ResearchPlanningService:
    return ResearchPlanningService(
        ResearchDependencies(
            question_planner=DemoQuestionPlanner(),
            academic_query_planner=DemoAcademicQueryPlanner(),
            paper_provider=DemoPaperProvider(),
        )
    )


def test_focused_question_searches_papers_without_interrupt() -> None:
    result = asyncio.run(
        make_service().plan(
            ResearchPlanRequest(
                question="长上下文模型能否在多跳问答任务中替代 RAG？"
            )
        )
    )

    assert result.status == "papers_ready"
    assert result.selected_question == result.original_question
    assert result.subquestions == []
    assert result.search_plan is not None
    assert result.search_plan.queries
    assert len(result.papers) == 3
    assert all(
        len(paper.matched_queries) == len(result.search_plan.queries)
        for paper in result.papers
    )
    assert [event.node for event in result.trace] == [
        "analyze_question",
        "finalize_question",
        "build_search_queries",
        "search_academic_papers",
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
    assert planned.papers == []
    assert resumed.status == "papers_ready"
    assert resumed.selected_question == planned.subquestions[1].question
    assert resumed.papers
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
    assert resumed.status == "papers_ready"
    assert resumed.selected_question == "长期对话中向量记忆压缩是否会损失关键事实？"
    assert resumed.search_plan is not None
    assert resumed.papers


def test_unknown_thread_is_rejected() -> None:
    with pytest.raises(ResearchThreadNotFound):
        asyncio.run(
            make_service().select(
                "missing-thread", ResearchSelectionRequest(option_id="sq_1")
            )
        )
