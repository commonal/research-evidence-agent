from __future__ import annotations

import asyncio

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from research_evidence_agent.api import create_app
from research_evidence_agent.graph.nodes import AgentDependencies
from research_evidence_agent.models import ResearchPlanRequest, ResearchSelectionRequest
from research_evidence_agent.persistence.repository import (
    ResearchRunRepository,
    create_database_engine,
)
from research_evidence_agent.research.academic import (
    DemoAcademicQueryPlanner,
    DemoPaperProvider,
)
from research_evidence_agent.research.nodes import ResearchDependencies
from research_evidence_agent.research.planner import DemoQuestionPlanner
from research_evidence_agent.research.service import ResearchPlanningService
from research_evidence_agent.providers.demo import DemoAnswerGenerator, DemoSearchProvider
from research_evidence_agent.service import SearchService


def make_repository(tmp_path) -> ResearchRunRepository:
    database_url = f"sqlite:///{(tmp_path / 'history.db').as_posix()}"
    repository = ResearchRunRepository(create_database_engine(database_url))
    repository.create_schema_for_tests()
    return repository


def make_service(repository: ResearchRunRepository) -> ResearchPlanningService:
    return ResearchPlanningService(
        ResearchDependencies(
            question_planner=DemoQuestionPlanner(),
            academic_query_planner=DemoAcademicQueryPlanner(),
            paper_provider=DemoPaperProvider(),
        ),
        run_store=repository,
    )


def test_completed_run_can_be_listed_and_reloaded(tmp_path) -> None:
    repository = make_repository(tmp_path)

    async def scenario():
        result = await make_service(repository).plan(
            ResearchPlanRequest(
                question="长上下文模型能否在多跳问答任务中替代 RAG？"
            )
        )
        return result, await repository.get(result.request_id), await repository.list(
            limit=20, offset=0
        )

    result, saved, history = asyncio.run(scenario())
    assert saved is not None
    assert saved.selected_question == result.selected_question
    assert saved.search_plan == result.search_plan
    assert saved.usage == result.usage
    assert [paper.arxiv_id for paper in saved.papers] == [
        paper.arxiv_id for paper in result.papers
    ]
    assert [paper.relevance_score for paper in saved.papers] == [
        paper.relevance_score for paper in result.papers
    ]
    assert [event.node for event in saved.trace] == [
        event.node for event in result.trace
    ]
    assert history.total == 1
    assert history.items[0].run_id == result.request_id
    assert history.items[0].paper_count == len(result.papers)
    assert history.items[0].top_relevance_score == result.papers[0].relevance_score
    repository.close()


def test_history_api_lists_and_returns_persisted_run(tmp_path) -> None:
    repository = make_repository(tmp_path)
    research_service = make_service(repository)
    search_service = SearchService(
        AgentDependencies(
            search_provider=DemoSearchProvider(),
            answer_generator=DemoAnswerGenerator(),
            max_results_per_query=5,
        )
    )
    client = TestClient(create_app(search_service, research_service))

    created = client.post(
        "/api/v1/research/plan",
        json={"question": "长上下文模型能否在多跳问答任务中替代 RAG？"},
    )
    assert created.status_code == 200
    run_id = created.json()["request_id"]

    history = client.get("/api/v1/research/runs?limit=10&offset=0")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["run_id"] == run_id

    detail = client.get(f"/api/v1/research/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["papers"][0]["relevance_score"] >= 0
    assert client.get("/api/v1/research/runs/missing").status_code == 404
    repository.close()


def test_interrupted_run_is_updated_in_place_after_selection(tmp_path) -> None:
    repository = make_repository(tmp_path)

    async def scenario():
        service = make_service(repository)
        planned = await service.plan(ResearchPlanRequest(question="大模型记忆"))
        before = await repository.get(planned.request_id)
        resumed = await service.select(
            planned.thread_id,
            ResearchSelectionRequest(option_id=planned.subquestions[0].id),
        )
        after = await repository.get(planned.request_id)
        history = await repository.list(limit=20, offset=0)
        return planned, before, resumed, after, history

    planned, before, resumed, after, history = asyncio.run(scenario())
    assert before is not None and before.status == "awaiting_selection"
    assert after is not None and after.status == "papers_ready"
    assert after.request_id == planned.request_id == resumed.request_id
    assert after.selected_question == planned.subquestions[0].question
    assert history.total == 1
    repository.close()


def test_initial_alembic_migration_creates_history_schema(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_database_engine(database_url)
    assert {
        "alembic_version",
        "research_runs",
        "workflow_events",
        "papers",
        "run_papers",
        "llm_calls",
    }.issubset(inspect(engine).get_table_names())
    engine.dispose()
