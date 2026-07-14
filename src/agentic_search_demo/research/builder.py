from __future__ import annotations

from langgraph.graph import END, StateGraph

from agentic_search_demo.research.nodes import (
    ResearchDependencies,
    analyze_question,
    finalize_question,
    generate_subquestions,
    route_after_analysis,
    wait_for_user_selection,
)
from agentic_search_demo.research.state import ResearchState


def build_research_planning_graph(deps: ResearchDependencies, *, checkpointer=None):
    async def analyze_node(state: ResearchState) -> dict:
        return await analyze_question(state, deps)

    async def decompose_node(state: ResearchState) -> dict:
        return await generate_subquestions(state, deps)

    workflow = StateGraph(ResearchState)
    workflow.add_node("analyze_question", analyze_node)
    workflow.add_node("generate_subquestions", decompose_node)
    workflow.add_node("wait_for_user_selection", wait_for_user_selection)
    workflow.add_node("finalize_question", finalize_question)

    workflow.set_entry_point("analyze_question")
    workflow.add_conditional_edges(
        "analyze_question",
        route_after_analysis,
        {"decompose": "generate_subquestions", "finalize": "finalize_question"},
    )
    workflow.add_edge("generate_subquestions", "wait_for_user_selection")
    workflow.add_edge("wait_for_user_selection", "finalize_question")
    workflow.add_edge("finalize_question", END)
    return workflow.compile(checkpointer=checkpointer)
