from __future__ import annotations

import os
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agentic_search_demo.config import Settings
from agentic_search_demo.graph.nodes import AgentDependencies
from agentic_search_demo.models import (
    HealthResponse,
    ResearchPlanRequest,
    ResearchPlanResponse,
    ResearchSelectionRequest,
    SearchRequest,
    SearchResponse,
)
from agentic_search_demo.providers.demo import DemoAnswerGenerator, DemoSearchProvider
from agentic_search_demo.research.nodes import (
    InvalidResearchSelection,
    ResearchDependencies,
)
from agentic_search_demo.research.planner import DemoQuestionPlanner
from agentic_search_demo.research.service import (
    ResearchPlanningService,
    ResearchThreadNotFound,
)
from agentic_search_demo.service import SearchService, sse_frame


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


def create_app(
    service: SearchService | None = None,
    research_service: ResearchPlanningService | None = None,
) -> FastAPI:
    service = service or create_service()
    research_service = research_service or ResearchPlanningService(
        ResearchDependencies(question_planner=DemoQuestionPlanner())
    )
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

