from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.coder import Coder
from agents.planner import Planner
from agents.reviewer import Reviewer
from core.graph import build_graph
from core.llm import create_chat_model
from core.state import DEFAULT_TOKEN_BUDGET, new_review_state
from tests.bug_cases import BUG_CASES, BugCase
from tests.conftest import FakeModel, FakeRAG
from tools.rag import StandardsRAG


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT_DIR / "reports" / "evaluation.md"


def _json_response(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def _fixture_graph(case: BugCase) -> Any:
    planner_model = FakeModel([_json_response({
        "goal": case["task"],
        "steps": ["复现问题", "修复实现", "运行验收测试"],
        "acceptance_criteria": ["pytest 用例通过"],
        "assumptions": [],
        "risks": [],
    })])
    coder_model = FakeModel([_json_response({
        "summary": "预置修复仅用于验证 Agent 图和测试执行链路。",
        "files": [
            {"path": path, "content": content}
            for path, content in case["fixed_files"].items()
        ],
    })])
    reviewer_model = FakeModel([_json_response({
        "approved": True,
        "summary": "fixture 响应；实际 pytest 仍由执行器运行。",
        "issues": [],
        "suggestions": [],
        "test_passed": True,
        "rag_context_used": [],
    })])
    return build_graph(
        Planner(planner_model),  # type: ignore[arg-type]
        Coder(coder_model),  # type: ignore[arg-type]
        Reviewer(reviewer_model, FakeRAG()),  # type: ignore[arg-type]
    )


def _run_case(graph: Any, case: BugCase, mode: str) -> dict[str, Any]:
    state = new_review_state(
        task=case["task"],
        max_retries=3,
        memory_context="评测集中的独立 Bug 修复任务。",
    )
    state["code"] = json.dumps(case["buggy_files"], ensure_ascii=False)
    result = graph.invoke(
        state,
        config={"configurable": {"thread_id": f"evaluation-{mode}-{case['name']}"}},
    )
    return {
        "name": case["name"],
        "approved": bool(result["review"]["approved"]),
        "status": str(result["status"]),
        "retry_count": int(result["retry_count"]),
        "total_token_usage": int(result["total_token_usage"]),
        "summary": str(result["review"]["summary"]),
    }


def _write_report(mode: str, results: list[dict[str, Any]]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    successful = sum(1 for item in results if item["approved"])
    count = len(results)
    success_rate = successful / count if count else 0.0
    average_retries = (
        sum(item["retry_count"] for item in results) / count if count else 0.0
    )
    budget_stops = sum(1 for item in results if item["status"] == "budget_exceeded")
    if mode == "fixture":
        token_text = "N/A（fixture 模式未调用真实模型）"
        note = (
            "> fixture 模式使用预置模型响应，只验证流程和测试执行链路；"
            "成功率不代表真实模型能力。"
        )
    else:
        token_text = (
            f"{sum(item['total_token_usage'] for item in results)}（累计服务端返回值）"
        )
        note = (
            "> live 模式使用真实 API。服务商未返回 Token usage 的调用不会被估算，"
            "因此数值可能不完整；预算上限按每个工作流分别计算。"
        )

    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    lines = [
        "# Multi-Agent Code Review Harness 评测报告",
        "",
        f"- 运行模式：`{mode}`",
        f"- 运行时间：`{timestamp}`",
        f"- 用例数：`{count}`",
        f"- 任务成功率：`{success_rate:.1%}`（{successful}/{count}）",
        f"- 平均重试次数：`{average_retries:.2f}`",
        f"- 单工作流 Token 预算：`{DEFAULT_TOKEN_BUDGET:,}`",
        f"- 预算熔断次数：`{budget_stops}`",
        f"- Token 总量：`{token_text}`",
        "",
        note,
        "",
        "| 用例 | 状态 | 通过 | 重试次数 | Token | 审查摘要 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for item in results:
        passed = "是" if item["approved"] else "否"
        tokens = str(item["total_token_usage"]) if mode == "live" else "N/A"
        summary = item["summary"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {item['name']} | {item['status']} | {passed} | "
            f"{item['retry_count']} | {tokens} | {summary} |"
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="运行代码审查 Harness 评测")
    parser.add_argument(
        "--mode",
        choices=("fixture", "live"),
        default="fixture",
        help="fixture 离线验证流程；live 调用真实模型 API",
    )
    args = parser.parse_args()
    results: list[dict[str, Any]] = []

    if args.mode == "fixture":
        for case in BUG_CASES:
            results.append(_run_case(_fixture_graph(case), case, args.mode))
    else:
        storage_dir = ROOT_DIR / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver

            model = create_chat_model()
            rag = StandardsRAG()
            rag.index_standards()
            with SqliteSaver.from_conn_string(
                str(storage_dir / "evaluation_checkpoints.sqlite")
            ) as saver:
                graph = build_graph(
                    Planner(model), Coder(model), Reviewer(model, rag),
                    checkpointer=saver,
                )
                for case in BUG_CASES:
                    results.append(_run_case(graph, case, args.mode))
        except Exception as exc:
            parser.error(f"live 评测失败：{type(exc).__name__}: {exc}")

    _write_report(args.mode, results)
    print(f"评测报告已生成：{REPORT_PATH}")
    print(f"模式：{args.mode}；通过：{sum(item['approved'] for item in results)}/{len(results)}")
    print(f"预算熔断：{sum(item['status'] == 'budget_exceeded' for item in results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
