from __future__ import annotations

from typing import Protocol

from research_evidence_agent.graph.state import AnswerDraft, Source


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, *, max_results: int) -> list[Source]: ...


class AnswerGenerator(Protocol):
    name: str

    async def generate(self, query: str, sources: list[Source]) -> AnswerDraft: ...

