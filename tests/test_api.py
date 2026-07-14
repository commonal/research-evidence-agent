from __future__ import annotations

import json

from fastapi.testclient import TestClient

from research_evidence_agent.api import create_app
from research_evidence_agent.graph.nodes import AgentDependencies
from research_evidence_agent.providers.demo import DemoAnswerGenerator, DemoSearchProvider
from research_evidence_agent.service import SearchService


def make_app():
    service = SearchService(
        AgentDependencies(
            search_provider=DemoSearchProvider(),
            answer_generator=DemoAnswerGenerator(),
            max_results_per_query=5,
        )
    )
    return create_app(service)


def parse_sse(payload: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for frame in payload.replace("\r\n", "\n").strip().split("\n\n"):
        event_name = "message"
        data = ""
        for line in frame.splitlines():
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data += line.removeprefix("data:").strip()
        if data:
            events.append((event_name, json.loads(data)))
    return events


def test_research_workspace_and_assets_are_served() -> None:
    client = TestClient(make_app())
    page = client.get("/")
    assert page.status_code == 200
    assert "Research Evidence Agent" in page.text
    assert 'id="workflow-timeline"' in page.text
    assert client.get("/assets/app.css").status_code == 200
    assert client.get("/assets/app.js").status_code == 200


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
    assert selected["status"] == "papers_ready"
    assert selected["selected_question"] == plan["subquestions"][0]["question"]
    assert selected["search_plan"]["queries"]
    assert selected["papers"]


def test_research_stream_reports_progress_and_resumes_selection() -> None:
    client = TestClient(make_app())
    response = client.post(
        "/api/v1/research/stream",
        json={"question": "大模型记忆"},
    )
    assert response.status_code == 200
    events = parse_sse(response.text)
    progress = [data for name, data in events if name == "progress"]
    result = [data for name, data in events if name == "result"][-1]
    assert progress[0]["node"] == "analyze_question"
    assert progress[0]["state"] == "running"
    assert result["status"] == "awaiting_selection"

    selection = client.post(
        f"/api/v1/research/{result['thread_id']}/selection/stream",
        json={"option_id": result["subquestions"][0]["id"]},
    )
    selection_events = parse_sse(selection.text)
    selection_result = [
        data for name, data in selection_events if name == "result"
    ][-1]
    assert selection_result["status"] == "papers_ready"
    assert selection_result["papers"]


def test_research_selection_validates_thread_and_payload() -> None:
    client = TestClient(make_app())
    assert client.post(
        "/api/v1/research/missing/selection", json={"option_id": "sq_1"}
    ).status_code == 404
    assert client.post(
        "/api/v1/research/missing/selection", json={}
    ).status_code == 422

