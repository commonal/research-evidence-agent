from __future__ import annotations

from langgraph.graph import END, StateGraph

from research_evidence_agent.research.nodes import (
    ResearchDependencies,
    analyze_question,
    finalize_question,
    generate_subquestions,
    build_search_queries,
    route_after_analysis,
    search_academic_papers,
    wait_for_user_selection,
)
from research_evidence_agent.research.state import ResearchState


def build_research_planning_graph(deps: ResearchDependencies, *, checkpointer=None):
    async def analyze_node(state: ResearchState) -> dict:
        return await analyze_question(state, deps)

    async def decompose_node(state: ResearchState) -> dict:
        return await generate_subquestions(state, deps)

    async def query_node(state: ResearchState) -> dict:
        return await build_search_queries(state, deps)

    async def paper_node(state: ResearchState) -> dict:
        return await search_academic_papers(state, deps)

    workflow = StateGraph(ResearchState)
    workflow.add_node("analyze_question", analyze_node)
    workflow.add_node("generate_subquestions", decompose_node)
    workflow.add_node("wait_for_user_selection", wait_for_user_selection)
    workflow.add_node("finalize_question", finalize_question)
    workflow.add_node("build_search_queries", query_node)
    workflow.add_node("search_academic_papers", paper_node)

    workflow.set_entry_point("analyze_question")
    workflow.add_conditional_edges(
        "analyze_question",
        route_after_analysis,
        {"decompose": "generate_subquestions", "finalize": "finalize_question"},
    )
    workflow.add_edge("generate_subquestions", "wait_for_user_selection")
    workflow.add_edge("wait_for_user_selection", "finalize_question")
    workflow.add_edge("finalize_question", "build_search_queries")
    workflow.add_edge("build_search_queries", "search_academic_papers")
    workflow.add_edge("search_academic_papers", END)
    return workflow.compile(checkpointer=checkpointer)
