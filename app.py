from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver

from agents.coder import Coder
from agents.planner import Planner
from agents.reviewer import Reviewer
from core.graph import build_graph
from core.llm import create_chat_model
from core.memory import SQLiteReviewMemory
from core.state import new_review_state
from tools.rag import StandardsRAG


ROOT_DIR = Path(__file__).resolve().parent
STORAGE_DIR = ROOT_DIR / "storage"


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(description="运行多智能体代码审查 Harness")
    parser.add_argument("--task", help="要实现或修复的研发任务")
    parser.add_argument("--thread-id", default="local-demo", help="同一会话复用该 ID")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=int(os.getenv("MAX_RETRIES", "3")),
    )
    args = parser.parse_args()

    task = (args.task or input("请输入研发任务：")).strip()
    if not task:
        parser.error("task 不能为空")
    if args.max_retries < 0:
        parser.error("max-retries 不能小于 0")

    try:
        model = create_chat_model()
        rag = StandardsRAG()
        rag.index_standards()
        timeout_seconds = max(1, int(os.getenv("CODE_RUN_TIMEOUT_SECONDS", "15")))
    except Exception as exc:
        print(f"初始化失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    memory = SQLiteReviewMemory(STORAGE_DIR / "review_memory.sqlite3")
    memory_context = memory.search(task)
    state = new_review_state(
        task=task,
        max_retries=args.max_retries,
        memory_context=memory_context,
    )

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    try:
        with SqliteSaver.from_conn_string(str(STORAGE_DIR / "checkpoints.sqlite")) as saver:
            graph = build_graph(
                Planner(model),
                Coder(model),
                Reviewer(model, rag, timeout_seconds=timeout_seconds),
                checkpointer=saver,
            )
            result = graph.invoke(
                state,
                config={"configurable": {"thread_id": args.thread_id}},
            )
    except Exception as exc:
        print(f"Agent 执行失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    memory.remember(
        task=task,
        status=result["status"],
        summary=result["review"]["summary"],
        issues=result["review"]["issues"],
    )
    print(json.dumps({
        "status": result["status"],
        "approved": result["review"]["approved"],
        "retry_count": result["retry_count"],
        "total_token_usage": result["total_token_usage"],
        "token_budget": result["token_budget"],
        "budget_message": result["budget_message"],
        "review": result["review"],
        "history": result["history"],
        "code_json": result["code"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["review"]["approved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
