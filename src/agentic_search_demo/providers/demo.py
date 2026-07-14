from __future__ import annotations

import hashlib
import re

from agentic_search_demo.graph.state import AnswerDraft, Citation, Source


_CORPUS: tuple[dict[str, str], ...] = (
    {
        "title": "LangGraph 状态图与可恢复执行",
        "url": "demo://langgraph/state",
        "content": (
            "LangGraph 用有状态图表达 Agent 流程。节点负责执行离散步骤，条件边负责路由，"
            "checkpointer 可以保存线程状态，使长任务能够暂停、恢复和重试。"
        ),
    },
    {
        "title": "面向复杂问题的 Agentic Search",
        "url": "demo://search/agentic",
        "content": (
            "Agentic Search 通常先分析问题并生成子查询，再并行访问多个搜索源。系统应评估证据"
            "是否充分，在缺少关键事实时改写查询并进行补充搜索，而不是只调用一次搜索接口。"
        ),
    },
    {
        "title": "工具调用与 MCP 适配",
        "url": "demo://tools/mcp",
        "content": (
            "MCP 为模型提供统一的工具发现和调用协议。生产 Agent 仍需要工具白名单、参数校验、"
            "超时、重试、审计日志和失败降级，不能把任意外部工具直接暴露给模型。"
        ),
    },
    {
        "title": "搜索结果的引用与事实校验",
        "url": "demo://search/citations",
        "content": (
            "带引用的搜索回答应保留来源 URL、标题、查询、正文片段和相关性分数。生成答案后，"
            "还要检查引用是否来自实际检索结果，以及引用内容能否支持答案中的关键结论。"
        ),
    },
    {
        "title": "FastAPI 流式 Agent 接口",
        "url": "demo://api/streaming",
        "content": (
            "FastAPI 可以通过 StreamingResponse 暴露 SSE。客户端能够看到分析问题、检索来源、"
            "证据评估和答案生成等节点事件，便于观察长时间 Agent 任务并定位失败步骤。"
        ),
    },
)


def _tokens(text: str) -> set[str]:
    # Character-level CJK tokens keep the offline demo useful for Chinese queries.
    return set(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower()))


def _source_id(url: str) -> str:
    return "src_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


class DemoSearchProvider:
    """Deterministic in-memory search provider for local demos and tests."""

    name = "demo"

    async def search(self, query: str, *, max_results: int) -> list[Source]:
        query_tokens = _tokens(query)
        ranked: list[tuple[float, dict[str, str]]] = []
        for item in _CORPUS:
            overlap = len(query_tokens & _tokens(item["title"] + item["content"]))
            score = overlap / max(1, len(query_tokens))
            ranked.append((score, item))

        ranked.sort(key=lambda item: (-item[0], item[1]["url"]))
        return [
            Source(
                id=_source_id(item["url"]),
                title=item["title"],
                url=item["url"],
                content=item["content"],
                score=round(min(0.99, max(0.01, score)), 4),
                source_type="demo",
                query=query,
            )
            for score, item in ranked[:max_results]
        ]


class DemoAnswerGenerator:
    """Extractive answerer that makes the graph runnable without an LLM key."""

    name = "demo"

    async def generate(self, query: str, sources: list[Source]) -> AnswerDraft:
        selected = sources[: min(4, len(sources))]
        if not selected:
            return {"answer": f"暂时没有找到足够证据回答：{query}", "citations": []}

        lines = [f"围绕“{query}”，检索结果给出的要点如下："]
        citations: list[Citation] = []
        for index, source in enumerate(selected, start=1):
            quote = source["content"][:160].strip()
            lines.append(f"{index}. {source['title']}：{quote} [{index}]")
            citations.append(
                Citation(
                    index=index,
                    source_id=source["id"],
                    title=source["title"],
                    url=source["url"],
                    quote=quote,
                )
            )
        lines.append("以上结论仅基于本次检索到的证据，引用编号对应来源列表。")
        return {"answer": "\n".join(lines), "citations": citations}

