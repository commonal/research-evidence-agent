from __future__ import annotations

import asyncio
import json

import httpx

from research_evidence_agent.models import ResearchPlanRequest
from research_evidence_agent.research.academic import (
    DemoPaperProvider,
    OpenAICompatibleAcademicQueryPlanner,
)
from research_evidence_agent.research.nodes import ResearchDependencies
from research_evidence_agent.research.planner import DemoQuestionPlanner
from research_evidence_agent.research.service import ResearchPlanningService


def test_openai_compatible_planner_collects_deepseek_usage() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "queries": [
                                        'all:"long context" AND all:"RAG"'
                                    ],
                                    "keywords": ["long context", "RAG"],
                                }
                            )
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 36,
                    "total_tokens": 156,
                    "prompt_cache_hit_tokens": 80,
                    "prompt_cache_miss_tokens": 40,
                    "completion_tokens_details": {"reasoning_tokens": 12},
                },
            },
        )

    planner = OpenAICompatibleAcademicQueryPlanner(
        api_key="test-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        transport=httpx.MockTransport(handler),
    )
    service = ResearchPlanningService(
        ResearchDependencies(
            question_planner=DemoQuestionPlanner(),
            academic_query_planner=planner,
            paper_provider=DemoPaperProvider(),
        )
    )

    result = asyncio.run(
        service.plan(
            ResearchPlanRequest(
                question="长上下文模型能否在多跳问答任务中替代 RAG？"
            )
        )
    )

    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert result.status == "papers_ready"
    assert result.usage.prompt_tokens == 120
    assert result.usage.completion_tokens == 36
    assert result.usage.prompt_cache_hit_tokens == 80
    assert result.usage.prompt_cache_miss_tokens == 40
    assert result.usage.reasoning_tokens == 12
    assert result.usage.calls[0].provider == "deepseek"
    assert result.usage.calls[0].model == "deepseek-v4-flash"
