from __future__ import annotations

from langgraph.graph import END, StateGraph

from agentic_search_demo.graph.nodes import (
    AgentDependencies,
    analyze_query,
    generate_answer,
    grade_evidence,
    plan_queries,
    repair_answer,
    rewrite_query,
    route_after_grade,
    route_after_verification,
    search_sources,
    verify_citations,
)
from agentic_search_demo.graph.state import SearchState


def build_graph(deps: AgentDependencies, *, checkpointer=None):
    """Build the search graph with injected providers for easy offline testing."""
    async def search_node(state: SearchState) -> dict:
        return await search_sources(state, deps)

    async def answer_node(state: SearchState) -> dict:
        return await generate_answer(state, deps)

    workflow = StateGraph(SearchState)
    workflow.add_node("analyze_query", analyze_query)
    workflow.add_node("plan_queries", plan_queries)
    workflow.add_node("search_sources", search_node)
    workflow.add_node("grade_evidence", grade_evidence)
    workflow.add_node("rewrite_query", rewrite_query)
    workflow.add_node("generate_answer", answer_node)
    workflow.add_node("verify_citations", verify_citations)
    workflow.add_node("repair_answer", repair_answer)

    workflow.set_entry_point("analyze_query")
    workflow.add_edge("analyze_query", "plan_queries")
    workflow.add_edge("plan_queries", "search_sources")
    workflow.add_edge("search_sources", "grade_evidence")
    workflow.add_conditional_edges(
        "grade_evidence",
        route_after_grade,
        {"rewrite": "rewrite_query", "generate": "generate_answer"},
    )
    workflow.add_edge("rewrite_query", "search_sources")
    workflow.add_edge("generate_answer", "verify_citations")
    workflow.add_conditional_edges(
        "verify_citations",
        route_after_verification,
        {"end": END, "repair": "repair_answer"},
    )
    workflow.add_edge("repair_answer", END)
    return workflow.compile(checkpointer=checkpointer)
