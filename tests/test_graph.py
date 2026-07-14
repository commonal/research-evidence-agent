from __future__ import annotations

import asyncio

from research_evidence_agent.graph.nodes import AgentDependencies
from research_evidence_agent.models import SearchRequest
from research_evidence_agent.providers.demo import DemoAnswerGenerator, DemoSearchProvider
from research_evidence_agent.service import SearchService


class ScriptedProvider:
    name = "scripted"

    def __init__(self, *, succeeds_on_followup: bool = True) -> None:
        self.calls: list[str] = []
        self.succeeds_on_followup = succeeds_on_followup

    async def search(self, query: str, *, max_results: int):
        self.calls.append(query)
        if self.succeeds_on_followup and "关键事实" in query:
            return [
                {
                    "id": "followup-source",
                    "title": "补充事实",
                    "url": "demo://followup",
                    "content": "补充查询找到了可以支持答案的关键事实。",
                    "score": 0.95,
                    "source_type": "scripted",
                    "query": query,
                }
            ]
        return []


def make_service(provider) -> SearchService:
    return SearchService(
        AgentDependencies(
            search_provider=provider,
            answer_generator=DemoAnswerGenerator(),
            max_results_per_query=5,
        )
    )


def test_demo_graph_returns_structured_citations() -> None:
    service = make_service(DemoSearchProvider())
    state = asyncio.run(
        service.run(
            SearchRequest(
                query="LangGraph 如何帮助构建可恢复的深度搜索 Agent？",
                mode="deep",
                max_iterations=2,
            )
        )
    )

    assert state["answer"]
    assert state["sources"]
    assert state["citations"]
    source_ids = {source["id"] for source in state["sources"]}
    assert {citation["source_id"] for citation in state["citations"]} <= source_ids
    assert state["verification_passed"] is True
    assert [event["node"] for event in state["trace"]][:3] == [
        "analyze_query",
        "plan_queries",
        "search_sources",
    ]


def test_insufficient_evidence_rewrites_and_searches_again() -> None:
    provider = ScriptedProvider()
    service = make_service(provider)
    state = asyncio.run(
        service.run(
            SearchRequest(
                query="一个需要补充证据的问题",
                mode="quick",
                max_iterations=2,
            )
        )
    )

    assert len(provider.calls) == 2
    assert state["search_round"] == 2
    assert "rewrite_query" in [event["node"] for event in state["trace"]]
    assert state["evidence_sufficient"] is True
    assert state["citations"][0]["url"] == "demo://followup"


def test_search_budget_stops_an_unproductive_loop() -> None:
    provider = ScriptedProvider(succeeds_on_followup=False)
    service = make_service(provider)
    state = asyncio.run(
        asyncio.wait_for(
            service.run(
                SearchRequest(query="永远没有结果的问题", mode="quick", max_iterations=2)
            ),
            timeout=2,
        )
    )

    assert len(provider.calls) == 2
    assert state["search_round"] == 2
    assert state["answer"]
    assert [event["node"] for event in state["trace"]].count("rewrite_query") == 1


def test_citation_url_cannot_be_fabricated() -> None:
    class BadAnswer:
        name = "bad"

        async def generate(self, query, sources):
            source = sources[0]
            return {
                "answer": "answer [1]",
                "citations": [
                    {
                        "index": 1,
                        "source_id": source["id"],
                        "title": source["title"],
                        "url": "https://attacker.invalid/fake",
                        "quote": "fake",
                    }
                ],
            }

    service = SearchService(
        AgentDependencies(
            search_provider=DemoSearchProvider(),
            answer_generator=BadAnswer(),
            max_results_per_query=3,
        )
    )
    state = asyncio.run(
        service.run(SearchRequest(query="搜索 Agent 的引用校验", mode="quick"))
    )
    source_by_id = {source["id"]: source for source in state["sources"]}
    assert state["verification_passed"] is True
    assert state["citations"]
    assert "attacker.invalid" not in state["citations"][0]["url"]
    for citation in state["citations"]:
        source = source_by_id[citation["source_id"]]
        assert citation["url"] == source["url"]
        assert citation["quote"] in source["content"]
    assert "repair_answer" in [event["node"] for event in state["trace"]]
