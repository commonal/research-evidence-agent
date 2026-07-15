from __future__ import annotations

import asyncio

import pytest

from research_evidence_agent.models import ResearchPlanRequest, ResearchSelectionRequest
from research_evidence_agent.research.academic import (
    DemoAcademicQueryPlanner,
    DemoPaperProvider,
)
from research_evidence_agent.research.nodes import ResearchDependencies, select_papers
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
    assert [paper.relevance_score for paper in result.papers] == sorted(
        [paper.relevance_score for paper in result.papers], reverse=True
    )
    assert all(0 <= paper.relevance_score <= 100 for paper in result.papers)
    assert result.papers[0].matched_keywords
    assert [event.node for event in result.trace] == [
        "analyze_question",
        "finalize_question",
        "build_search_queries",
        "search_academic_papers",
        "select_papers",
    ]


def test_simple_relevance_score_uses_word_boundaries_and_query_coverage() -> None:
    def paper(arxiv_id: str, title: str, abstract: str, rank: int) -> dict:
        return {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": ["Researcher"],
            "abstract": abstract,
            "published_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
            "categories": ["cs.CL"],
            "abs_url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "matched_queries": ['all:"RAG"'],
            "rank": rank,
        }

    result = select_papers(
        {
            "search_plan": {
                "queries": ['all:"RAG"', 'all:"retrieval augmented generation"'],
                "keywords": ["RAG"],
            },
            "papers": [
                paper(
                    "2401.00001",
                    "Storage Systems for Language Models",
                    "We study storage efficiency.",
                    1,
                ),
                paper(
                    "2402.00002",
                    "RAG for Question Answering",
                    "RAG improves grounded generation.",
                    2,
                ),
            ],
            "trace": [],
        }
    )

    assert [item["arxiv_id"] for item in result["papers"]] == [
        "2402.00002",
        "2401.00001",
    ]
    assert result["papers"][0]["relevance_score"] == 93
    assert result["papers"][0]["matched_keywords"] == ["RAG"]
    assert result["papers"][1]["relevance_score"] == 8
    assert result["papers"][1]["matched_keywords"] == []


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
