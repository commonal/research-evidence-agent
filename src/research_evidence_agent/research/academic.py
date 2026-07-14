from __future__ import annotations

import json
import re
from typing import Protocol

import httpx

from research_evidence_agent.research.state import AcademicQueryPlanResult, Paper


class AcademicQueryPlanner(Protocol):
    name: str

    async def plan(self, question: str) -> AcademicQueryPlanResult: ...


class PaperProvider(Protocol):
    name: str

    async def search(self, query: str, *, max_results: int) -> list[Paper]: ...


class DemoAcademicQueryPlanner:
    """Offline query planner with a small AI/CS terminology map."""

    name = "demo_academic_query_planner"
    _terms = {
        "大模型": "large language models",
        "长上下文": "long context language models",
        "多跳问答": "multi-hop question answering",
        "检索增强": "retrieval augmented generation",
        "记忆": "memory mechanisms",
        "智能体": "LLM agents",
        "向量": "vector retrieval",
    }

    async def plan(self, question: str) -> AcademicQueryPlanResult:
        lowered = question.lower()
        translated = [english for chinese, english in self._terms.items() if chinese in question]
        ascii_terms = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", lowered)
        keywords = _dedupe([*translated, *ascii_terms])
        if not keywords:
            keywords = [question]
        primary = " AND ".join(f'all:"{_escape_term(term)}"' for term in keywords[:3])
        broad = f'all:"{_escape_term(keywords[0])}"'
        return {
            "queries": _dedupe([primary, broad])[:3],
            "keywords": keywords[:8],
        }


class OpenAICompatibleAcademicQueryPlanner:
    """Generate Arxiv search expressions through an OpenAI-compatible API."""

    name = "openai_compatible_academic_query_planner"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY is required for the LLM academic query planner")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def plan(self, question: str) -> AcademicQueryPlanResult:
        prompt = (
            "Convert the research question into 1 to 3 concise Arxiv API search_query "
            "expressions. Use English academic terminology and fields such as all:, ti:, "
            "or abs:. Return JSON only with keys queries and keywords. Each query must be "
            "a string and may use AND/OR. Do not invent paper titles.\n\n"
            f"Research question: {question}"
        )
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
        response_payload = response.json()
        content = response_payload["choices"][0]["message"]["content"]
        payload = json.loads(_strip_json_fence(str(content)))
        queries = [_normalize_arxiv_query(item) for item in payload.get("queries", [])]
        keywords = [" ".join(str(item).split()) for item in payload.get("keywords", [])]
        queries = _dedupe([item for item in queries if item])[:3]
        keywords = _dedupe([item for item in keywords if item])[:8]
        if not queries:
            raise ValueError("LLM query planner returned no usable Arxiv queries")
        usage = _usage_record(
            response_payload.get("usage", {}),
            provider="deepseek" if "deepseek.com" in self.base_url else "openai_compatible",
            model=str(response_payload.get("model") or self.model),
        )
        return {"queries": queries, "keywords": keywords, "usage": usage}


class DemoPaperProvider:
    """Deterministic papers for local development without network access."""

    name = "demo_arxiv"

    async def search(self, query: str, *, max_results: int) -> list[Paper]:
        rows = (
            (
                "2401.00001",
                "Long-Context Language Models and Retrieval-Augmented Generation",
                "We compare long-context language models with retrieval-augmented "
                "generation on knowledge-intensive tasks.",
                ["cs.CL", "cs.AI"],
            ),
            (
                "2402.00002",
                "Memory Mechanisms for Large Language Model Agents",
                "This paper studies external memory, retrieval, and compression for "
                "language-model agents.",
                ["cs.AI"],
            ),
            (
                "2403.00003",
                "Evaluating Multi-Hop Question Answering with Long Contexts",
                "We evaluate evidence retrieval and reasoning in multi-hop question "
                "answering benchmarks.",
                ["cs.CL"],
            ),
        )
        return [
            Paper(
                arxiv_id=arxiv_id,
                title=title,
                authors=["Demo Researcher"],
                abstract=abstract,
                published_at="2024-01-01T00:00:00+00:00",
                updated_at="2024-01-01T00:00:00+00:00",
                categories=categories,
                abs_url=f"https://arxiv.org/abs/{arxiv_id}",
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
                matched_queries=[query],
                rank=index,
            )
            for index, (arxiv_id, title, abstract, categories) in enumerate(
                rows[:max_results], start=1
            )
        ]


def _normalize_arxiv_query(value: object) -> str:
    query = " ".join(str(value).split())[:500]
    if not query:
        return ""
    if re.search(r"(?:^|\s)(?:all|ti|au|abs|cat):", query):
        return query
    return f'all:"{_escape_term(query)}"'


def _escape_term(value: str) -> str:
    return " ".join(value.replace('"', " ").split())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _strip_json_fence(value: str) -> str:
    value = value.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    return value


def _usage_record(payload: object, *, provider: str, model: str) -> dict:
    usage = payload if isinstance(payload, dict) else {}
    details = usage.get("completion_tokens_details")
    details = details if isinstance(details, dict) else {}
    return {
        "operation": "build_search_queries",
        "provider": provider,
        "model": model,
        "prompt_tokens": _integer(usage.get("prompt_tokens")),
        "completion_tokens": _integer(usage.get("completion_tokens")),
        "total_tokens": _integer(usage.get("total_tokens")),
        "prompt_cache_hit_tokens": _integer(
            usage.get("prompt_cache_hit_tokens")
        ),
        "prompt_cache_miss_tokens": _integer(
            usage.get("prompt_cache_miss_tokens")
        ),
        "reasoning_tokens": _integer(details.get("reasoning_tokens")),
    }


def _integer(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
