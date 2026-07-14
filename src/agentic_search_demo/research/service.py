from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agentic_search_demo.models import (
    ResearchPlanRequest,
    ResearchPlanResponse,
    ResearchSelectionRequest,
)
from agentic_search_demo.research.builder import build_research_planning_graph
from agentic_search_demo.research.nodes import ResearchDependencies
from agentic_search_demo.research.state import ResearchState


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
        request_id = str(uuid.uuid4())
        thread_id = request.thread_id or request_id
        initial = ResearchState(
            request_id=request_id,
            thread_id=thread_id,
            original_question=request.question,
            selected_question="",
            is_broad=False,
            status="analyzing",
            subquestions=[],
            trace=[],
        )
        config = self._config(thread_id)
        await self.graph.ainvoke(initial, config=config)
        return await self._response(config)

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
            trace=state.get("trace", []),
        )

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}
