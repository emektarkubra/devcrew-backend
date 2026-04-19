from langgraph.graph import StateGraph, END
from app.services.agents.team_mode.nodes import (
    supervisor_node,
    validator_node,
    aggregator_node,
    make_nodes,
)


def route_supervisor(state: dict) -> str:
    current = state.get("current_agent", "")
    if current == "aggregator":
        return "aggregator"
    if current in ["codebase", "pr_review", "test", "documentation"]:
        return current
    return END


def route_validator(state: dict) -> str:
    agent = state.get("current_agent", "")
    completed = state.get("completed", [])
    if agent not in completed and state.get("retry_count", 0) > 0:
        return agent
    return "supervisor"


def build_graph(db, user_id: int):
    codebase_node, pr_review_node, test_node, doc_node = make_nodes(db, user_id)

    builder = StateGraph(dict)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("codebase", codebase_node)
    builder.add_node("pr_review", pr_review_node)
    builder.add_node("test", test_node)
    builder.add_node("documentation", doc_node)
    builder.add_node("validator", validator_node)
    builder.add_node("aggregator", aggregator_node)

    builder.set_entry_point("supervisor")

    builder.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "codebase": "codebase",
            "pr_review": "pr_review",
            "test": "test",
            "documentation": "documentation",
            "aggregator": "aggregator",
        },
    )

    for agent in ["codebase", "pr_review", "test", "documentation"]:
        builder.add_edge(agent, "validator")

    builder.add_conditional_edges(
        "validator",
        route_validator,
        {
            "codebase": "codebase",
            "pr_review": "pr_review",
            "test": "test",
            "documentation": "documentation",
            "supervisor": "supervisor",
        },
    )

    builder.add_edge("aggregator", END)

    return builder.compile()
