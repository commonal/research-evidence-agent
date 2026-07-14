from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from research_evidence_agent.graph.builder import build_graph
from research_evidence_agent.graph.nodes import AgentDependencies
from research_evidence_agent.graph.state import SearchState
from research_evidence_agent.models import SearchMode, SearchRequest, SearchResponse


@dataclass(slots=True)
class SearchService:
    deps: AgentDependencies
    checkpointer: Any = field(default=None, repr=False)
    graph: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.checkpointer is None:
            self.checkpointer = MemorySaver()
        self.graph = build_graph(self.deps, checkpointer=self.checkpointer)

    def _initial_state(self, request: SearchRequest) -> SearchState:
        request_id = str(uuid.uuid4())
        return SearchState(
            request_id=request_id,
            thread_id=request.thread_id or request_id,
            query=request.query,
            requested_mode=request.mode.value,
            max_iterations=request.max_iterations,
            search_round=0,
            sub_queries=[],
            searched_queries=[],
            sources=[],
            missing_topics=[],
            evidence_score=0.0,
            evidence_sufficient=False,
            answer="",
            citations=[],
            invalid_citation_count=0,
            verification_passed=False,
            trace=[],
        )

    async def run(self, request: SearchRequest) -> SearchState:
        initial = self._initial_state(request)
        return await self.graph.ainvoke(
            initial,
            config={"configurable": {"thread_id": initial["thread_id"]}},
        )

    async def stream(self, request: SearchRequest) -> AsyncIterator[dict[str, Any]]:
        """Yield node progress followed by one serializable final result."""
        initial = self._initial_state(request)
        last_state: SearchState | None = None
        emitted_events = 0
        async for state in self.graph.astream(
            initial,
            config={"configurable": {"thread_id": initial["thread_id"]}},
            stream_mode="values",
        ):
            last_state = state
            events = state.get("trace", [])[emitted_events:]
            for event in events:
                emitted_events += 1
                yield {"event": "progress", "data": event}
        if last_state is None:
            last_state = initial
        yield {"event": "result", "data": self.to_response(last_state).model_dump(mode="json")}

    @staticmethod
    def to_response(state: SearchState) -> SearchResponse:
        return SearchResponse(
            request_id=state["request_id"],
            thread_id=state["thread_id"],
            query=state["query"],
            mode=SearchMode(state.get("mode", "standard")),
            answer=state.get("answer", ""),
            citations=state.get("citations", []),
            invalid_citation_count=state.get("invalid_citation_count", 0),
            sources=state.get("sources", []),
            evidence_score=state.get("evidence_score", 0.0),
            evidence_sufficient=state.get("evidence_sufficient", False),
            search_rounds=state.get("search_round", 0),
            trace=state.get("trace", []),
        )


def sse_frame(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
