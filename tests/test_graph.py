from __future__ import annotations

import json

from agents.coder import Coder
from agents.planner import Planner
from agents.reviewer import Reviewer
from core.graph import build_graph
from core.state import new_review_state
from tests.conftest import FakeModel, FakeRAG


def _plan_response() -> str:
    return json.dumps({
        "goal": "修复加法函数",
        "steps": ["检查实现", "修复逻辑", "运行测试"],
        "acceptance_criteria": ["2 + 3 的结果为 5"],
        "assumptions": [],
        "risks": [],
    })


def _coder_response(source: str) -> str:
    return json.dumps({
        "summary": "更新加法函数实现。",
        "files": [
            {"path": "solution.py", "content": source},
            {
                "path": "test_add.py",
                "content": (
                    "from solution import add\n\n"
                    "def test_add():\n    assert add(2, 3) == 5\n"
                ),
            },
        ],
    })


def _review_response(approved: bool) -> str:
    return json.dumps({
        "approved": approved,
        "summary": "审查完成。",
        "issues": [] if approved else ["测试未通过，需要修复实现。"],
        "suggestions": [],
        "test_passed": approved,
        "rag_context_used": [],
    })


def test_graph_retries_then_finishes_after_fix() -> None:
    planner = Planner(FakeModel([_plan_response()]))  # type: ignore[arg-type]
    coder = Coder(FakeModel([
        _coder_response("def add(a, b):\n    return a - b\n"),
        _coder_response("def add(a, b):\n    return a + b\n"),
    ]))  # type: ignore[arg-type]
    reviewer = Reviewer(
        FakeModel([_review_response(False), _review_response(True)]),  # type: ignore[arg-type]
        FakeRAG(),  # type: ignore[arg-type]
    )

    graph = build_graph(planner, coder, reviewer)
    result = graph.invoke(new_review_state("实现加法函数", max_retries=3))

    assert result["status"] == "approved"
    assert result["review"]["approved"] is True
    assert result["retry_count"] == 1


def test_graph_stops_after_retry_limit() -> None:
    planner = Planner(FakeModel([_plan_response()]))  # type: ignore[arg-type]
    coder = Coder(FakeModel(
        [_coder_response("def add(a, b):\n    return a - b\n")],
        repeat_last=True,
    ))  # type: ignore[arg-type]
    reviewer = Reviewer(
        FakeModel([_review_response(True)], repeat_last=True),  # type: ignore[arg-type]
        FakeRAG(),  # type: ignore[arg-type]
    )

    graph = build_graph(planner, coder, reviewer)
    result = graph.invoke(new_review_state("实现加法函数", max_retries=3))

    assert result["status"] == "needs_revision"
    assert result["retry_count"] == 4
    assert result["review"]["approved"] is False
