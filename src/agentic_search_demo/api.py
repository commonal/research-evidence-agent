from __future__ import annotations

import os
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agentic_search_demo.config import Settings
from agentic_search_demo.graph.nodes import AgentDependencies
from agentic_search_demo.models import HealthResponse, SearchRequest, SearchResponse
from agentic_search_demo.providers.demo import DemoAnswerGenerator, DemoSearchProvider
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


def create_app(service: SearchService | None = None) -> FastAPI:
    service = service or create_service()
    settings = Settings.from_env()
    app = FastAPI(title="Research Evidence Agent", version="0.1.0")
    app.state.search_service = service
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

    return app


app = create_app()

