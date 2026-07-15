from __future__ import annotations

import asyncio
from typing import Protocol

from sqlalchemy import Engine, create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from research_evidence_agent.models import (
    LLMUsageSummaryResponse,
    PaperResponse,
    ResearchPlanResponse,
    ResearchRunListResponse,
    ResearchRunSummaryResponse,
    ResearchTraceResponse,
)
from research_evidence_agent.persistence.tables import (
    Base,
    LLMCallTable,
    PaperTable,
    ResearchRunTable,
    RunPaperTable,
    WorkflowEventTable,
    utc_now,
)


class ResearchRunStore(Protocol):
    async def save(self, response: ResearchPlanResponse) -> None: ...

    async def get(self, run_id: str) -> ResearchPlanResponse | None: ...

    async def list(
        self, *, limit: int, offset: int
    ) -> ResearchRunListResponse: ...


class ResearchRunRepository:
    """Idempotent SQLAlchemy repository for product-facing research history."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._session_factory = sessionmaker(
            bind=engine,
            class_=Session,
            expire_on_commit=False,
        )

    @classmethod
    def from_url(cls, database_url: str) -> "ResearchRunRepository":
        return cls(create_database_engine(database_url))

    async def save(self, response: ResearchPlanResponse) -> None:
        await asyncio.to_thread(self._save, response)

    async def get(self, run_id: str) -> ResearchPlanResponse | None:
        return await asyncio.to_thread(self._get, run_id)

    async def list(
        self, *, limit: int, offset: int
    ) -> ResearchRunListResponse:
        return await asyncio.to_thread(self._list, limit, offset)

    def create_schema_for_tests(self) -> None:
        Base.metadata.create_all(self.engine)

    @property
    def backend_name(self) -> str:
        return self.engine.dialect.name

    def close(self) -> None:
        self.engine.dispose()

    def _save(self, response: ResearchPlanResponse) -> None:
        payload = response.model_dump(mode="json")
        now = utc_now()
        with self._session_factory.begin() as session:
            run = session.get(ResearchRunTable, response.request_id)
            if run is None:
                run = ResearchRunTable(
                    id=response.request_id,
                    thread_id=response.thread_id,
                    status=response.status,
                    original_question=response.original_question,
                    selected_question=response.selected_question,
                    created_at=now,
                    updated_at=now,
                )
                session.add(run)

            run.thread_id = response.thread_id
            run.status = response.status
            run.original_question = response.original_question
            run.selected_question = response.selected_question
            run.subquestions = payload["subquestions"]
            run.search_plan = payload["search_plan"]
            run.search_errors = payload["search_errors"]
            run.paper_count = len(response.papers)
            run.top_relevance_score = max(
                (paper.relevance_score for paper in response.papers),
                default=None,
            )
            run.updated_at = now
            if response.status in {"papers_ready", "no_results"}:
                run.completed_at = run.completed_at or now
            else:
                run.completed_at = None
            session.flush()

            self._replace_run_children(session, response)

    def _replace_run_children(
        self,
        session: Session,
        response: ResearchPlanResponse,
    ) -> None:
        run_id = response.request_id
        session.execute(
            delete(WorkflowEventTable).where(WorkflowEventTable.run_id == run_id)
        )
        session.execute(delete(LLMCallTable).where(LLMCallTable.run_id == run_id))
        session.execute(delete(RunPaperTable).where(RunPaperTable.run_id == run_id))

        for sequence, event in enumerate(response.trace, start=1):
            session.add(
                WorkflowEventTable(
                    run_id=run_id,
                    sequence=sequence,
                    node=event.node,
                    message=event.message,
                    details=event.details,
                )
            )

        for sequence, call in enumerate(response.usage.calls, start=1):
            session.add(
                LLMCallTable(
                    run_id=run_id,
                    sequence=sequence,
                    **call.model_dump(mode="python"),
                )
            )

        for display_order, paper in enumerate(response.papers, start=1):
            stored_paper = session.get(PaperTable, paper.arxiv_id)
            if stored_paper is None:
                stored_paper = PaperTable(arxiv_id=paper.arxiv_id)
                session.add(stored_paper)
            _update_paper(stored_paper, paper)
            session.add(
                RunPaperTable(
                    run_id=run_id,
                    arxiv_id=paper.arxiv_id,
                    display_order=display_order,
                    source_rank=paper.rank,
                    relevance_score=paper.relevance_score,
                    matched_keywords=paper.matched_keywords,
                    matched_queries=paper.matched_queries,
                )
            )

    def _get(self, run_id: str) -> ResearchPlanResponse | None:
        with self._session_factory() as session:
            run = session.get(ResearchRunTable, run_id)
            if run is None:
                return None
            events = session.scalars(
                select(WorkflowEventTable)
                .where(WorkflowEventTable.run_id == run_id)
                .order_by(WorkflowEventTable.sequence)
            ).all()
            calls = session.scalars(
                select(LLMCallTable)
                .where(LLMCallTable.run_id == run_id)
                .order_by(LLMCallTable.sequence)
            ).all()
            paper_rows = session.execute(
                select(RunPaperTable, PaperTable)
                .join(PaperTable, PaperTable.arxiv_id == RunPaperTable.arxiv_id)
                .where(RunPaperTable.run_id == run_id)
                .order_by(RunPaperTable.display_order)
            ).all()

            usage_calls = [_call_payload(call) for call in calls]
            usage = LLMUsageSummaryResponse(
                **{
                    field: sum(item[field] for item in usage_calls)
                    for field in _TOKEN_FIELDS
                },
                calls=usage_calls,
            )
            papers = [
                _paper_response(run_paper, paper)
                for run_paper, paper in paper_rows
            ]
            return ResearchPlanResponse(
                request_id=run.id,
                thread_id=run.thread_id,
                status=run.status,
                original_question=run.original_question,
                selected_question=run.selected_question,
                subquestions=run.subquestions,
                search_plan=run.search_plan,
                usage=usage,
                papers=papers,
                search_errors=run.search_errors,
                trace=[
                    ResearchTraceResponse(
                        node=event.node,
                        message=event.message,
                        details=event.details,
                    )
                    for event in events
                ],
            )

    def _list(self, limit: int, offset: int) -> ResearchRunListResponse:
        with self._session_factory() as session:
            total = (
                session.scalar(select(func.count()).select_from(ResearchRunTable))
                or 0
            )
            rows = session.scalars(
                select(ResearchRunTable)
                .order_by(ResearchRunTable.updated_at.desc(), ResearchRunTable.id)
                .limit(limit)
                .offset(offset)
            ).all()
            return ResearchRunListResponse(
                items=[_run_summary(row) for row in rows],
                total=total,
                limit=limit,
                offset=offset,
            )


_TOKEN_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "reasoning_tokens",
)


def create_database_engine(database_url: str) -> Engine:
    normalized_url = normalize_database_url(database_url)
    options: dict = {"pool_pre_ping": True}
    if normalized_url in {"sqlite://", "sqlite:///:memory:"}:
        options.update(
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(normalized_url, **options)


def normalize_database_url(database_url: str) -> str:
    value = database_url.strip()
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def _update_paper(stored: PaperTable, paper: PaperResponse) -> None:
    stored.title = paper.title
    stored.authors = paper.authors
    stored.abstract = paper.abstract
    stored.published_at = paper.published_at
    stored.updated_at = paper.updated_at
    stored.categories = paper.categories
    stored.abs_url = paper.abs_url
    stored.pdf_url = paper.pdf_url
    stored.metadata_updated_at = utc_now()


def _call_payload(call: LLMCallTable) -> dict:
    return {
        "operation": call.operation,
        "provider": call.provider,
        "model": call.model,
        **{field: getattr(call, field) for field in _TOKEN_FIELDS},
    }


def _paper_response(run_paper: RunPaperTable, paper: PaperTable) -> PaperResponse:
    return PaperResponse(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        published_at=paper.published_at,
        updated_at=paper.updated_at,
        categories=paper.categories,
        abs_url=paper.abs_url,
        pdf_url=paper.pdf_url,
        matched_queries=run_paper.matched_queries,
        rank=run_paper.source_rank,
        relevance_score=run_paper.relevance_score,
        matched_keywords=run_paper.matched_keywords,
    )


def _run_summary(run: ResearchRunTable) -> ResearchRunSummaryResponse:
    return ResearchRunSummaryResponse(
        run_id=run.id,
        thread_id=run.thread_id,
        status=run.status,
        original_question=run.original_question,
        selected_question=run.selected_question,
        paper_count=run.paper_count,
        top_relevance_score=run.top_relevance_score,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )
