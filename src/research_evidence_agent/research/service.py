from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from research_evidence_agent.models import (
    LLMUsageSummaryResponse,
    ResearchPlanRequest,
    ResearchPlanResponse,
    ResearchSelectionRequest,
)
from research_evidence_agent.research.builder import build_research_planning_graph
from research_evidence_agent.research.nodes import ResearchDependencies
from research_evidence_agent.research.state import ResearchState


class ResearchThreadNotFound(LookupError):
    """Raised when a selection targets an unknown planning thread."""


@dataclass(slots=True)
class ResearchPlanningService:
    deps: ResearchDependencies
    checkpointer: Any = field(default=None, repr=False)
    graph: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.checkpointer is None:
            self.checkpointer = MemorySaver()
        self.graph = build_research_planning_graph(
            self.deps, checkpointer=self.checkpointer
        )

    async def plan(self, request: ResearchPlanRequest) -> ResearchPlanResponse:
        initial = self._initial_state(request)
        config = self._config(initial["thread_id"])
        await self.graph.ainvoke(initial, config=config)
        return await self._response(config)

    async def stream_plan(
        self, request: ResearchPlanRequest
    ) -> AsyncIterator[dict[str, Any]]:
        initial = self._initial_state(request)
        config = self._config(initial["thread_id"])
        async for item in self._stream_graph(
            initial,
            config=config,
            initial_node="analyze_question",
            emitted_events=0,
        ):
            yield item

    async def select(
        self, thread_id: str, request: ResearchSelectionRequest
    ) -> ResearchPlanResponse:
        config = self._config(thread_id)
        snapshot = await self.graph.aget_state(config)
        if not snapshot.values:
            raise ResearchThreadNotFound(thread_id)
        if "wait_for_user_selection" not in snapshot.next:
            raise ResearchThreadNotFound(
                f"thread {thread_id!r} is not awaiting a question selection"
            )
        await self.graph.ainvoke(
            Command(resume=request.model_dump(exclude_none=True)),
            config=config,
        )
        return await self._response(config)

    async def stream_select(
        self, thread_id: str, request: ResearchSelectionRequest
    ) -> AsyncIterator[dict[str, Any]]:
        config = self._config(thread_id)
        snapshot = await self.graph.aget_state(config)
        self._validate_selection_snapshot(thread_id, snapshot)
        command = Command(resume=request.model_dump(exclude_none=True))
        async for item in self._stream_graph(
            command,
            config=config,
            initial_node="wait_for_user_selection",
            emitted_events=len(snapshot.values.get("trace", [])),
        ):
            yield item

    def _initial_state(self, request: ResearchPlanRequest) -> ResearchState:
        request_id = str(uuid.uuid4())
        return ResearchState(
            request_id=request_id,
            thread_id=request.thread_id or request_id,
            original_question=request.question,
            selected_question="",
            is_broad=False,
            status="analyzing",
            subquestions=[],
            search_plan={"queries": [], "keywords": []},
            llm_usage=[],
            papers=[],
            search_errors=[],
            trace=[],
        )

    async def _stream_graph(
        self,
        graph_input: ResearchState | Command,
        *,
        config: dict,
        initial_node: str,
        emitted_events: int,
    ) -> AsyncIterator[dict[str, Any]]:
        yield {"event": "progress", "data": _running_event(initial_node)}
        async for state in self.graph.astream(
            graph_input,
            config=config,
            stream_mode="values",
        ):
            events = state.get("trace", [])[emitted_events:]
            for event in events:
                emitted_events += 1
                yield {
                    "event": "progress",
                    "data": {**event, "state": "completed"},
                }
                next_node = _next_node(event["node"], state)
                if next_node:
                    yield {
                        "event": "progress",
                        "data": _running_event(next_node),
                    }

        response = await self._response(config)
        if response.status == "awaiting_selection":
            yield {
                "event": "progress",
                "data": {
                    **_running_event("wait_for_user_selection"),
                    "state": "waiting",
                    "message": "等待用户选择或修改研究问题",
                },
            }
        if response.usage.calls:
            yield {
                "event": "usage",
                "data": response.usage.model_dump(mode="json"),
            }
        yield {
            "event": "result",
            "data": response.model_dump(mode="json"),
        }

    async def _response(self, config: dict) -> ResearchPlanResponse:
        snapshot = await self.graph.aget_state(config)
        state: ResearchState = snapshot.values
        return ResearchPlanResponse(
            request_id=state["request_id"],
            thread_id=state["thread_id"],
            status=state["status"],
            original_question=state["original_question"],
            selected_question=state.get("selected_question") or None,
            subquestions=state.get("subquestions", []),
            search_plan=state.get("search_plan"),
            usage=_summarize_usage(state.get("llm_usage", [])),
            papers=state.get("papers", []),
            search_errors=state.get("search_errors", []),
            trace=state.get("trace", []),
        )

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    @staticmethod
    def _validate_selection_snapshot(thread_id: str, snapshot: Any) -> None:
        if not snapshot.values:
            raise ResearchThreadNotFound(thread_id)
        if "wait_for_user_selection" not in snapshot.next:
            raise ResearchThreadNotFound(
                f"thread {thread_id!r} is not awaiting a question selection"
            )


_RUNNING_MESSAGES = {
    "analyze_question": "正在判断问题范围与研究边界",
    "generate_subquestions": "正在拆解候选研究问题",
    "wait_for_user_selection": "正在处理用户选择",
    "finalize_question": "正在确认最终研究问题",
    "build_search_queries": "正在调用模型生成学术检索式",
    "search_academic_papers": "正在检索并合并 arXiv 论文",
}


def _running_event(node: str) -> dict[str, Any]:
    return {
        "node": node,
        "state": "running",
        "message": _RUNNING_MESSAGES[node],
        "details": {},
    }


def _next_node(node: str, state: ResearchState) -> str | None:
    if node == "analyze_question":
        return "generate_subquestions" if state.get("is_broad") else "finalize_question"
    return {
        "generate_subquestions": "wait_for_user_selection",
        "wait_for_user_selection": "finalize_question",
        "finalize_question": "build_search_queries",
        "build_search_queries": "search_academic_papers",
    }.get(node)


def _summarize_usage(records: list[dict[str, Any]]) -> LLMUsageSummaryResponse:
    fields = (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "reasoning_tokens",
    )
    totals = {
        field: sum(int(record.get(field, 0)) for record in records)
        for field in fields
    }
    return LLMUsageSummaryResponse(**totals, calls=records)
