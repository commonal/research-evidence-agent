from __future__ import annotations

import re
from dataclasses import dataclass

from langgraph.types import interrupt

from research_evidence_agent.research.academic import (
    AcademicQueryPlanner,
    PaperProvider,
)
from research_evidence_agent.research.planner import QuestionPlanner
from research_evidence_agent.research.state import (
    Paper,
    ResearchState,
    ResearchTraceEvent,
    SubQuestion,
)


class InvalidResearchSelection(ValueError):
    """Raised when a resume payload does not identify a valid question."""


@dataclass(frozen=True, slots=True)
class ResearchDependencies:
    question_planner: QuestionPlanner
    academic_query_planner: AcademicQueryPlanner
    paper_provider: PaperProvider
    max_results_per_query: int = 5


def _trace(node: str, message: str, **details) -> ResearchTraceEvent:
    return ResearchTraceEvent(node=node, message=message, details=details)


def _append_trace(
    state: ResearchState, event: ResearchTraceEvent
) -> list[ResearchTraceEvent]:
    return [*state.get("trace", []), event]


async def analyze_question(
    state: ResearchState, deps: ResearchDependencies
) -> dict:
    question = state["original_question"]
    is_broad = await deps.question_planner.is_broad(question)
    message = "问题范围较宽，需要用户选择具体研究问题" if is_broad else "问题范围明确，可以进入研究"
    return {
        "is_broad": is_broad,
        "status": "analyzing",
        "trace": _append_trace(
            state,
            _trace(
                "analyze_question",
                message,
                is_broad=is_broad,
                planner=deps.question_planner.name,
            ),
        ),
    }


async def generate_subquestions(
    state: ResearchState, deps: ResearchDependencies
) -> dict:
    questions = await deps.question_planner.decompose(state["original_question"])
    if not 3 <= len(questions) <= 5:
        raise ValueError("question planner must return between 3 and 5 subquestions")
    return {
        "subquestions": questions,
        "status": "awaiting_selection",
        "trace": _append_trace(
            state,
            _trace(
                "generate_subquestions",
                f"已生成 {len(questions)} 个候选研究问题",
                subquestion_count=len(questions),
            ),
        ),
    }


def wait_for_user_selection(state: ResearchState) -> dict:
    selection = interrupt(
        {
            "kind": "research_question_selection",
            "original_question": state["original_question"],
            "subquestions": state.get("subquestions", []),
        }
    )
    selected = _resolve_selection(state.get("subquestions", []), selection)
    return {
        "selected_question": selected,
        "status": "ready",
        "trace": _append_trace(
            state,
            _trace(
                "wait_for_user_selection",
                "用户已确认具体研究问题",
                selected_question=selected,
            ),
        ),
    }


def finalize_question(state: ResearchState) -> dict:
    selected = state.get("selected_question") or state["original_question"]
    return {
        "selected_question": selected,
        "status": "ready",
        "trace": _append_trace(
            state,
            _trace(
                "finalize_question",
                "研究问题已就绪，下一阶段将进入 Arxiv 检索",
                selected_question=selected,
            ),
        ),
    }


async def build_search_queries(
    state: ResearchState, deps: ResearchDependencies
) -> dict:
    selected = state["selected_question"]
    plan = await deps.academic_query_planner.plan(selected)
    queries = [
        " ".join(query.split())
        for query in plan.get("queries", [])
        if query.strip()
    ]
    if not queries:
        raise ValueError("academic query planner returned no queries")
    usage = plan.get("usage")
    search_plan = {"queries": queries[:3], "keywords": plan.get("keywords", [])[:8]}
    usage_records = state.get("llm_usage", [])
    if usage:
        usage_records = [*usage_records, usage]
    return {
        "search_plan": search_plan,
        "llm_usage": usage_records,
        "status": "searching",
        "trace": _append_trace(
            state,
            _trace(
                "build_search_queries",
                f"已生成 {len(search_plan['queries'])} 个 Arxiv 检索式",
                queries=search_plan["queries"],
                planner=deps.academic_query_planner.name,
                usage=usage,
            ),
        ),
    }


async def search_academic_papers(
    state: ResearchState, deps: ResearchDependencies
) -> dict:
    merged: dict[str, Paper] = {}
    errors: list[str] = []
    queries = state["search_plan"]["queries"]
    for query in queries:
        try:
            results = await deps.paper_provider.search(
                query, max_results=deps.max_results_per_query
            )
        except Exception as exc:  # preserve partial results from other queries
            errors.append(f"{query}: {exc}")
            continue
        for paper in results:
            existing = merged.get(paper["arxiv_id"])
            if existing is None:
                merged[paper["arxiv_id"]] = paper
                continue
            existing["matched_queries"] = _dedupe(
                [*existing["matched_queries"], *paper["matched_queries"]]
            )
            existing["rank"] = min(existing["rank"], paper["rank"])

    papers = sorted(
        merged.values(),
        key=lambda paper: (paper["rank"], paper["published_at"], paper["arxiv_id"]),
    )
    return {
        "papers": papers,
        "search_errors": errors,
        "status": "searching",
        "trace": _append_trace(
            state,
            _trace(
                "search_academic_papers",
                f"学术检索完成，得到 {len(papers)} 篇去重论文",
                provider=deps.paper_provider.name,
                query_count=len(queries),
                paper_count=len(papers),
                errors=errors,
            ),
        ),
    }


def select_papers(state: ResearchState) -> dict:
    """Score and reorder papers without dropping recall candidates."""

    search_plan = state.get("search_plan", {"queries": [], "keywords": []})
    terms = _score_terms(
        search_plan.get("keywords", []),
        search_plan.get("queries", []),
    )
    query_count = max(1, len(search_plan.get("queries", [])))
    scored: list[Paper] = []

    for paper in state.get("papers", []):
        normalized_title = _normalize_match_text(paper["title"])
        normalized_abstract = _normalize_match_text(paper["abstract"])
        title_hits = [term for term in terms if _matches(normalized_title, term)]
        abstract_hits = [term for term in terms if _matches(normalized_abstract, term)]
        matched_keywords = _dedupe([*title_hits, *abstract_hits])
        term_count = max(1, len(terms))
        query_coverage = min(
            1.0,
            len(_dedupe(paper.get("matched_queries", []))) / query_count,
        )
        relevance_score = min(
            100,
            int(
                50 * len(title_hits) / term_count
                + 35 * len(abstract_hits) / term_count
                + 15 * query_coverage
                + 0.5
            ),
        )
        scored.append(
            Paper(
                **paper,
                relevance_score=relevance_score,
                matched_keywords=matched_keywords,
            )
        )

    scored.sort(
        key=lambda paper: (
            -paper.get("relevance_score", 0),
            paper["rank"],
            paper["arxiv_id"],
        )
    )
    status = "papers_ready" if scored else "no_results"
    return {
        "papers": scored,
        "status": status,
        "trace": _append_trace(
            state,
            _trace(
                "select_papers",
                f"已对 {len(scored)} 篇论文完成轻量相关性评分",
                paper_count=len(scored),
                score_terms=terms,
                top_score=scored[0]["relevance_score"] if scored else 0,
                scoring_method="title_50+abstract_35+query_coverage_15",
            ),
        ),
    }


def route_after_analysis(state: ResearchState) -> str:
    return "decompose" if state.get("is_broad") else "finalize"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _score_terms(keywords: list[str], queries: list[str]) -> list[str]:
    terms = _dedupe([" ".join(str(value).split()) for value in keywords])
    if not terms:
        terms = _dedupe(
            [
                match.strip()
                for query in queries
                for match in re.findall(r'"([^"]+)"', query)
            ]
        )
    return terms


def _normalize_match_text(value: str) -> str:
    normalized = re.sub(r"[^\w]+", " ", value.casefold()).replace("_", " ")
    return " ".join(normalized.split())


def _matches(normalized_text: str, term: str) -> bool:
    normalized_term = _normalize_match_text(term)
    if not normalized_term:
        return False
    if normalized_term.isascii():
        return f" {normalized_term} " in f" {normalized_text} "
    return normalized_term in normalized_text


def _resolve_selection(
    subquestions: list[SubQuestion], selection: object
) -> str:
    if not isinstance(selection, dict):
        raise InvalidResearchSelection("selection payload must be an object")

    custom_question = " ".join(str(selection.get("question") or "").split())
    if custom_question:
        if len(custom_question) < 3:
            raise InvalidResearchSelection("custom question is too short")
        return custom_question

    option_id = str(selection.get("option_id") or "")
    for option in subquestions:
        if option["id"] == option_id:
            return option["question"]
    raise InvalidResearchSelection("option_id does not match a candidate question")
