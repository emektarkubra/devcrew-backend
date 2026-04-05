from app.services.agents.team_mode.graph import build_graph


async def run_team_mode(
    owner:           str,
    repo_name:       str,
    user_id:         int,
    access_token:    str,
    selected_agents: list[str],
    db,
) -> dict:

    graph = build_graph(db, user_id)

    initial_state = {
        "repo":            f"{owner}/{repo_name}",
        "owner":           owner,
        "repo_name":       repo_name,
        "access_token":    access_token,
        "selected_agents": selected_agents,
        "completed":       [],
        "current_agent":   "",
        "retry_count":     0,
        "results":         {},
        "health_score":    None,
        "health_summary":  None,
        "top_actions":     None,
    }

    final_state = await graph.ainvoke(initial_state)

    return {
        "repo":         f"{owner}/{repo_name}",
        "agents":       selected_agents,
        "results":      final_state.get("results", {}),
        "health_score": final_state.get("health_score", 0),
        "summary":      final_state.get("health_summary", ""),
        "top_actions":  final_state.get("top_actions", []),
    }