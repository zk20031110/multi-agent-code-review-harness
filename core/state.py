from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class ReviewResult(TypedDict):
    approved: bool
    summary: str
    issues: list[str]
    suggestions: list[str]
    test_output: str
    rag_context: str


class HistoryEvent(TypedDict):
    agent: str
    summary: str


class ReviewState(TypedDict):
    task: str
    plan: list[str]
    code: str
    review: ReviewResult
    memory_context: str
    retry_count: int
    max_retries: int
    status: str
    token_budget: int
    budget_message: str
    total_token_usage: Annotated[int, operator.add]
    history: Annotated[list[HistoryEvent], operator.add]


DEFAULT_TOKEN_BUDGET = 50_000


def new_review_state(
    task: str,
    max_retries: int = 3,
    memory_context: str = "",
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> ReviewState:
    """创建一轮审查任务的初始状态。"""
    if max_retries < 0:
        raise ValueError("max_retries 不能小于 0")
    if token_budget <= 0:
        raise ValueError("token_budget 必须大于 0")

    return {
        "task": task,
        "plan": [],
        "code": "",
        "review": {
            "approved": False,
            "summary": "",
            "issues": [],
            "suggestions": [],
            "test_output": "",
            "rag_context": "",
        },
        "memory_context": memory_context,
        "retry_count": 0,
        "max_retries": max_retries,
        "status": "pending",
        "token_budget": token_budget,
        "budget_message": "",
        "total_token_usage": 0,
        "history": [],
    }
