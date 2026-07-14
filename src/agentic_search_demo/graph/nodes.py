from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from typing import Callable

from agentic_search_demo.graph.state import Citation, SearchState, Source, TraceEvent
from agentic_search_demo.providers.base import AnswerGenerator, SearchProvider


@dataclass(frozen=True, slots=True)
class AgentDependencies:
    search_provider: SearchProvider
    answer_generator: AnswerGenerator
    max_results_per_query: int = 5


def _trace(
    state: SearchState,
    node: str,
    message: str,
    *,
    details: dict | None = None,
) -> TraceEvent:
    return TraceEvent(
        node=node,
        message=message,
        search_round=state.get("search_round", 0),
        details=details or {},
    )


def _append_trace(state: SearchState, event: TraceEvent) -> list[TraceEvent]:
    return [*state.get("trace", []), event]


def _resolve_mode(requested: str, query: str) -> str:
    if requested != "auto":
        return requested
    deep_markers = ("对比", "分析", "为什么", "如何构建", "最新", "研究", "compare", "analyze")
    if len(query) >= 70 or any(marker in query.lower() for marker in deep_markers):
        return "deep"
    if len(query) >= 30:
        return "standard"
    return "quick"


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for query in queries:
        normalized = " ".join(query.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def analyze_query(state: SearchState) -> dict:
    query = state["query"]
    mode = _resolve_mode(state.get("requested_mode", "auto"), query)
    event = _trace(
        state,
        "analyze_query",
        f"已将问题路由到 {mode} 搜索模式",
        details={"query_length": len(query), "mode": mode},
    )
    return {"mode": mode, "trace": _append_trace(state, event)}


def plan_queries(state: SearchState) -> dict:
    query = state["query"]
    mode = state["mode"]
    if mode == "quick":
        queries = [query]
    elif mode == "standard":
        queries = [query, f"{query} 官方资料", f"{query} 实践案例"]
    else:
        queries = [
            query,
            f"{query} 核心机制",
            f"{query} 优缺点与限制",
            f"{query} 官方文档 实现细节",
        ]
    queries = _dedupe_queries(queries)
    event = _trace(
        state,
        "plan_queries",
        f"已生成 {len(queries)} 个研究子问题",
        details={"sub_queries": queries},
    )
    return {"sub_queries": queries, "trace": _append_trace(state, event)}


def _stable_source_id(url: str, content: str) -> str:
    return "src_" + hashlib.sha1(f"{url}\n{content}".encode("utf-8")).hexdigest()[:10]


def _normalize_source(raw: Source | dict, query: str) -> Source | None:
    url = str(raw.get("url") or raw.get("href") or "").strip()
    content = str(raw.get("content") or raw.get("body") or "").strip()
    if not url or not content:
        return None
    return Source(
        id=str(raw.get("id") or _stable_source_id(url, content)),
        title=str(raw.get("title") or url),
        url=url,
        content=content,
        score=float(raw.get("score") or 0.01),
        source_type=str(raw.get("source_type") or "search"),
        query=str(raw.get("query") or query),
    )


async def search_sources(state: SearchState, deps: AgentDependencies) -> dict:
    queries = state.get("sub_queries", [state["query"]])

    async def run_one(query: str) -> tuple[str, list[Source] | Exception]:
        try:
            return query, await deps.search_provider.search(
                query, max_results=deps.max_results_per_query
            )
        except Exception as exc:  # Keep one failing provider from killing other queries.
            return query, exc

    batches = await asyncio.gather(*(run_one(query) for query in queries))
    merged: dict[str, Source] = {
        source["url"]: source for source in state.get("sources", [])
    }
    errors: list[str] = []
    successful_queries: list[str] = []
    for query, result in batches:
        if isinstance(result, Exception):
            errors.append(f"{query}: {result}")
            continue
        successful_queries.append(query)
        for raw in result:
            source = _normalize_source(raw, query)
            if source is None:
                continue
            previous = merged.get(source["url"])
            if previous is None or source["score"] > previous["score"]:
                merged[source["url"]] = source

    sources = sorted(merged.values(), key=lambda item: (-item["score"], item["url"]))
    next_round = state.get("search_round", 0) + 1
    event = _trace(
        {**state, "search_round": next_round},
        "search_sources",
        f"第 {next_round} 轮检索完成，累计得到 {len(sources)} 个来源",
        details={
            "queries": queries,
            "successful_queries": successful_queries,
            "errors": errors,
            "source_count": len(sources),
        },
    )
    return {
        "sources": sources,
        "searched_queries": [*state.get("searched_queries", []), *successful_queries],
        "search_round": next_round,
        "trace": _append_trace({**state, "search_round": next_round}, event),
    }


def grade_evidence(state: SearchState) -> dict:
    sources = state.get("sources", [])
    mode = state.get("mode", "standard")
    required_count = {"quick": 1, "standard": 2, "deep": 3}.get(mode, 2)
    quality_sources = [source for source in sources if source["score"] >= 0.08]
    average_score = (
        sum(source["score"] for source in quality_sources) / len(quality_sources)
        if quality_sources
        else 0.0
    )
    covered_queries = {
        source["query"] for source in quality_sources if source.get("query")
    }
    expected_queries = set(state.get("sub_queries", []))
    coverage = len(covered_queries & expected_queries) / max(1, len(expected_queries))
    sufficient = (
        len(quality_sources) >= required_count
        and average_score >= 0.12
        and (coverage >= 0.25 or mode == "quick")
    )
    missing = [
        query
        for query in state.get("sub_queries", [])
        if query not in covered_queries
    ]
    if not missing and not sufficient:
        missing = [f"{state['query']} 补充证据与反例"]
    event = _trace(
        state,
        "grade_evidence",
        "证据充分，进入回答生成" if sufficient else "证据不足，需要判断是否补充搜索",
        details={
            "quality_source_count": len(quality_sources),
            "average_score": round(average_score, 4),
            "coverage": round(coverage, 4),
            "required_count": required_count,
            "missing_topics": missing,
        },
    )
    return {
        "evidence_score": round(min(1.0, average_score * (0.5 + coverage / 2)), 4),
        "evidence_sufficient": sufficient,
        "missing_topics": missing,
        "trace": _append_trace(state, event),
    }


def rewrite_query(state: SearchState) -> dict:
    missing = state.get("missing_topics", [])
    rewritten = _dedupe_queries(
        [
            f"{topic} 原始资料 关键事实" if topic else f"{state['query']} 补充证据"
            for topic in missing[:3]
        ]
    )
    if not rewritten:
        rewritten = [f"{state['query']} 补充证据"]
    event = _trace(
        state,
        "rewrite_query",
        f"根据证据缺口生成 {len(rewritten)} 个补充查询",
        details={"missing_topics": missing, "rewritten_queries": rewritten},
    )
    return {"sub_queries": rewritten, "trace": _append_trace(state, event)}


async def generate_answer(state: SearchState, deps: AgentDependencies) -> dict:
    sources = sorted(state.get("sources", []), key=lambda item: -item["score"])
    draft = await deps.answer_generator.generate(state["query"], sources)
    event = _trace(
        state,
        "generate_answer",
        f"已生成回答并关联 {len(draft['citations'])} 条引用",
        details={"answer_length": len(draft["answer"]), "citation_count": len(draft["citations"])},
    )
    return {
        "answer": draft["answer"],
        "citations": draft["citations"],
        "trace": _append_trace(state, event),
    }


def verify_citations(state: SearchState) -> dict:
    source_by_id = {source["id"]: source for source in state.get("sources", [])}
    citations: list[Citation] = []
    invalid_count = 0
    for citation in state.get("citations", []):
        source = source_by_id.get(citation.get("source_id", ""))
        if source is None or citation.get("url") != source["url"]:
            invalid_count += 1
            continue
        # Rebuild metadata from the retrieved source so a generator cannot invent URLs.
        candidate_quote = str(citation.get("quote") or "").strip()
        quote = (
            candidate_quote
            if candidate_quote and candidate_quote in source["content"]
            else source["content"][:160]
        )
        citations.append(
            Citation(
                index=len(citations) + 1,
                source_id=source["id"],
                title=source["title"],
                url=source["url"],
                quote=quote,
            )
        )
    valid = bool(state.get("answer", "").strip()) and bool(citations) and invalid_count == 0
    event = _trace(
        state,
        "verify_citations",
        "引用校验通过" if valid else "引用校验未通过，执行修复",
        details={
            "valid_citation_count": len(citations),
            "invalid_citation_count": invalid_count,
        },
    )
    return {
        "citations": citations,
        "invalid_citation_count": invalid_count,
        "verification_passed": valid,
        "trace": _append_trace(state, event),
    }


def repair_answer(state: SearchState) -> dict:
    answer = state.get("answer", "").strip()
    citations = state.get("citations", [])
    if state.get("invalid_citation_count", 0) and citations:
        # Remove stale numeric markers before adding the normalized references.
        answer = re.sub(r"\s*\[\d+\]", "", answer).strip()
        answer += "\n\n可验证来源："
        answer += " ".join(
            f"[{citation['index']}] {citation['title']}" for citation in citations
        )
    elif not citations and state.get("sources"):
        source = state["sources"][0]
        quote = source["content"][:160]
        citations = [
            Citation(
                index=1,
                source_id=source["id"],
                title=source["title"],
                url=source["url"],
                quote=quote,
            )
        ]
        answer = answer or "当前证据不足，无法给出可靠结论。"
        answer += f"\n\n参考来源：[1] {source['title']}"
    event = _trace(
        state,
        "repair_answer",
        "已补充可追溯来源并结束本轮任务",
        details={"citation_count": len(citations)},
    )
    return {
        "answer": answer or "当前没有可用证据。",
        "citations": citations,
        "verification_passed": bool(citations),
        "trace": _append_trace(state, event),
    }


def route_after_grade(state: SearchState) -> str:
    if state.get("evidence_sufficient"):
        return "generate"
    if state.get("search_round", 0) < state.get("max_iterations", 1):
        return "rewrite"
    return "generate"


def route_after_verification(state: SearchState) -> str:
    return "end" if state.get("verification_passed") else "repair"
