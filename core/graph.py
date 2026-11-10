from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from core.state import ReviewState
from core.trace import trace_node


AgentNode = Callable[[ReviewState], dict[str, Any]]
Route = Literal["coder", "reviewer", "budget_stop", "end"]


def _over_budget(state: ReviewState) -> bool:
    return state["total_token_usage"] >= state["token_budget"]


def _stop_for_budget(state: ReviewState) -> dict[str, Any]:
    used = state["total_token_usage"]
    budget = state["token_budget"]
    message = (
        f"预算超限：累计用量 {used:,} Token，预算上限 {budget:,} Token；"
        "工作流已停止。"
    )
    review = dict(state["review"])
    review.update({
        "approved": False,
        "summary": message,
        "issues": [message],
    })
    return {
        "status": "budget_exceeded",
        "budget_message": message,
        "review": review,
        "history": [{"agent": "budget_guard", "summary": message}],
    }


def _after_planner(state: ReviewState) -> Route:
    return "budget_stop" if _over_budget(state) else "coder"


def _after_coder(state: ReviewState) -> Route:
    if _over_budget(state):
        return "budget_stop"
    if state["status"] == "coder_error":
        return "coder" if state["retry_count"] <= state["max_retries"] else "end"
    return "reviewer"


def supervisor_route(state: ReviewState) -> Route:
    """通过后结束；未通过且未耗尽返工次数时退回 Coder。"""
    if _over_budget(state):
        return "budget_stop"
    if state["status"] == "approved":
        return "end"
    if state["retry_count"] <= state["max_retries"]:
        return "coder"
    return "end"


def build_graph(
    planner_node: AgentNode,
    coder_node: AgentNode,
    reviewer_node: AgentNode,
    checkpointer: Any | None = None,
) -> Any:
    builder = StateGraph(ReviewState)
    builder.add_node("planner", trace_node("planner")(planner_node))
    builder.add_node("coder", trace_node("coder")(coder_node))
    builder.add_node("reviewer", trace_node("reviewer")(reviewer_node))
    builder.add_node("budget_stop", trace_node("budget_guard")(_stop_for_budget))
    builder.add_edge(START, "planner")
    builder.add_conditional_edges(
        "planner",
        _after_planner,
        {"coder": "coder", "budget_stop": "budget_stop"},
    )
    builder.add_conditional_edges(
        "coder",
        _after_coder,
        {
            "coder": "coder",
            "reviewer": "reviewer",
            "budget_stop": "budget_stop",
            "end": END,
        },
    )
    builder.add_conditional_edges(
        "reviewer",
        supervisor_route,
        {"coder": "coder", "budget_stop": "budget_stop", "end": END},
    )
    builder.add_edge("budget_stop", END)
    return builder.compile(checkpointer=checkpointer)
