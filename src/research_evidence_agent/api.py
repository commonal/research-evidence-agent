from __future__ import annotations

import os
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from research_evidence_agent.config import Settings
from research_evidence_agent.graph.nodes import AgentDependencies
from research_evidence_agent.models import (
    HealthResponse,
    ResearchPlanRequest,
    ResearchPlanResponse,
    ResearchSelectionRequest,
    SearchRequest,
    SearchResponse,
)
from research_evidence_agent.providers.arxiv import ArxivPaperProvider
from research_evidence_agent.providers.demo import DemoAnswerGenerator, DemoSearchProvider
from research_evidence_agent.research.academic import (
    DemoAcademicQueryPlanner,
    DemoPaperProvider,
    OpenAICompatibleAcademicQueryPlanner,
)
from research_evidence_agent.research.nodes import (
    InvalidResearchSelection,
    ResearchDependencies,
)
from research_evidence_agent.research.planner import DemoQuestionPlanner
from research_evidence_agent.research.service import (
    ResearchPlanningService,
    ResearchThreadNotFound,
)
from research_evidence_agent.service import SearchService, sse_frame


def create_service(settings: Settings | None = None) -> SearchService:
    settings = settings or Settings.from_env()
    if settings.search_provider != "demo":
        raise ValueError(f"Unsupported SEARCH_PROVIDER: {settings.search_provider}")
    if settings.answer_provider != "demo":
        raise ValueError(f"Unsupported ANSWER_PROVIDER: {settings.answer_provider}")

    search_provider = DemoSearchProvider()
    answer_generator = DemoAnswerGenerator()

    return SearchService(
        AgentDependencies(
            search_provider=search_provider,
            answer_generator=answer_generator,
            max_results_per_query=settings.search_max_results,
        )
    )


def create_research_service(
    settings: Settings | None = None,
) -> ResearchPlanningService:
    settings = settings or Settings.from_env()

    if settings.academic_query_planner == "demo":
        academic_query_planner = DemoAcademicQueryPlanner()
    elif settings.academic_query_planner == "openai_compatible":
        if not settings.llm_api_key:
            raise ValueError(
                "LLM_API_KEY is required when ACADEMIC_QUERY_PLANNER="
                "openai_compatible"
            )
        academic_query_planner = OpenAICompatibleAcademicQueryPlanner(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
    else:
        raise ValueError(
            "Unsupported ACADEMIC_QUERY_PLANNER: "
            f"{settings.academic_query_planner}"
        )

    if settings.research_paper_provider == "demo":
        paper_provider = DemoPaperProvider()
    elif settings.research_paper_provider == "arxiv":
        paper_provider = ArxivPaperProvider(
            api_url=settings.arxiv_api_url,
            min_interval_seconds=settings.arxiv_min_interval_seconds,
        )
    else:
        raise ValueError(
            "Unsupported RESEARCH_PAPER_PROVIDER: "
            f"{settings.research_paper_provider}"
        )

    return ResearchPlanningService(
        ResearchDependencies(
            question_planner=DemoQuestionPlanner(),
            academic_query_planner=academic_query_planner,
            paper_provider=paper_provider,
            max_results_per_query=settings.research_max_results_per_query,
        )
    )


def create_app(
    service: SearchService | None = None,
    research_service: ResearchPlanningService | None = None,
) -> FastAPI:
    service = service or create_service()
    research_service = research_service or create_research_service()
    settings = Settings.from_env()
    app = FastAPI(title="Research Evidence Agent", version="0.1.0")
    app.state.search_service = service
    app.state.research_service = research_service
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            graph="langgraph",
            search_provider=service.deps.search_provider.name,
            answer_provider=service.deps.answer_generator.name,
        )

    @app.post("/api/v1/search", response_model=SearchResponse)
    async def search(request: SearchRequest) -> SearchResponse:
        state = await service.run(request)
        return service.to_response(state)

    @app.post("/api/v1/search/stream")
    async def search_stream(request: SearchRequest) -> StreamingResponse:
        async def events() -> AsyncIterator[str]:
            async for item in service.stream(request):
                yield sse_frame(item["event"], item["data"])

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/v1/research/plan", response_model=ResearchPlanResponse)
    async def plan_research(request: ResearchPlanRequest) -> ResearchPlanResponse:
        return await research_service.plan(request)

    @app.post(
        "/api/v1/research/{thread_id}/selection",
        response_model=ResearchPlanResponse,
    )
    async def select_research_question(
        thread_id: str, request: ResearchSelectionRequest
    ) -> ResearchPlanResponse:
        try:
            return await research_service.select(thread_id, request)
        except ResearchThreadNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidResearchSelection as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


app = create_app()

