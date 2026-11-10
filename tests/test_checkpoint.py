from __future__ import annotations

import json
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from agents.coder import Coder
from agents.planner import Planner
from agents.reviewer import Reviewer
from core.graph import build_graph
from core.state import new_review_state
from tests.conftest import FakeModel, FakeRAG


def test_sqlite_checkpoint_saves_thread_state(tmp_path: Path) -> None:
    plan = json.dumps({
        "goal": "create a function",
        "steps": ["write code", "test code"],
        "acceptance_criteria": ["test passes"],
        "assumptions": [],
        "risks": [],
    })
    code = json.dumps({
        "summary": "Create add function.",
        "files": [
            {"path": "solution.py", "content": "def add(a, b):\n    return a + b\n"},
            {
                "path": "test_add.py",
                "content": (
                    "from solution import add\n\n"
                    "def test_add():\n    assert add(2, 3) == 5\n"
                ),
            },
        ],
    })
    review = json.dumps({
        "approved": True,
        "summary": "Tests pass.",
        "issues": [],
        "suggestions": [],
    })

    nodes = (
        Planner(FakeModel([plan])),  # type: ignore[arg-type]
        Coder(FakeModel([code])),  # type: ignore[arg-type]
        Reviewer(FakeModel([review]), FakeRAG()),  # type: ignore[arg-type]
    )
    config = {"configurable": {"thread_id": "checkpoint-test"}}
    with SqliteSaver.from_conn_string(str(tmp_path / "checkpoints.sqlite")) as saver:
        graph = build_graph(*nodes, checkpointer=saver)
        result = graph.invoke(new_review_state("create add function"), config=config)
        snapshot = graph.get_state(config)

    assert result["review"]["approved"] is True
    assert snapshot.values["status"] == "approved"
    assert snapshot.values["history"]
