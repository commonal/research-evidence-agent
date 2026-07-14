from __future__ import annotations

from fastapi.testclient import TestClient

from agentic_search_demo.api import create_app
from agentic_search_demo.graph.nodes import AgentDependencies
from agentic_search_demo.providers.demo import DemoAnswerGenerator, DemoSearchProvider
from agentic_search_demo.service import SearchService


def make_app():
    service = SearchService(
        AgentDependencies(
            search_provider=DemoSearchProvider(),
            answer_generator=DemoAnswerGenerator(),
            max_results_per_query=5,
        )
    )
    return create_app(service)


def test_health_and_search_endpoint() -> None:
    client = TestClient(make_app())
    assert client.get("/health").json()["graph"] == "langgraph"
    response = client.post(
        "/api/v1/search",
        json={"query": "LangGraph 的状态图有什么作用？", "mode": "quick"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["citations"]
    assert body["mode"] == "quick"


def test_stream_endpoint_emits_progress_and_result() -> None:
    client = TestClient(make_app())
    response = client.post(
        "/api/v1/search/stream",
        json={"query": "MCP 工具调用如何做权限控制？", "mode": "quick"},
    )
    assert response.status_code == 200
    assert "event: progress" in response.text
    assert "event: result" in response.text


def test_request_validation() -> None:
    client = TestClient(make_app())
    response = client.post("/api/v1/search", json={"query": "x"})
    assert response.status_code == 422


def test_research_question_planning_and_selection() -> None:
    client = TestClient(make_app())
    plan_response = client.post(
        "/api/v1/research/plan", json={"question": "大模型记忆"}
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["status"] == "awaiting_selection"
    assert len(plan["subquestions"]) == 4

    selection_response = client.post(
        f"/api/v1/research/{plan['thread_id']}/selection",
        json={"option_id": plan["subquestions"][0]["id"]},
    )
    assert selection_response.status_code == 200
    selected = selection_response.json()
    assert selected["status"] == "ready"
    assert selected["selected_question"] == plan["subquestions"][0]["question"]


def test_research_selection_validates_thread_and_payload() -> None:
    client = TestClient(make_app())
    assert client.post(
        "/api/v1/research/missing/selection", json={"option_id": "sq_1"}
    ).status_code == 404
    assert client.post(
        "/api/v1/research/missing/selection", json={}
    ).status_code == 422

