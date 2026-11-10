from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar


PROJECT_DIR = Path(__file__).resolve().parents[1]
TRACE_PATH = PROJECT_DIR / "trace.log"
_TRACE_LOCK = threading.Lock()
Node = TypeVar("Node", bound=Callable[..., dict[str, Any]])


def _input_summary(state: Mapping[str, Any]) -> dict[str, Any]:
    code = state.get("code", "")
    try:
        decoded = json.loads(code) if code else {}
        file_count = len(decoded) if isinstance(decoded, dict) else None
    except (TypeError, json.JSONDecodeError):
        file_count = None

    task = state.get("task", "")
    review = state.get("review", {})
    return {
        "task_chars": len(task) if isinstance(task, str) else 0,
        "status": state.get("status"),
        "code_chars": len(code) if isinstance(code, str) else 0,
        "code_file_count": file_count,
        "retry_count": state.get("retry_count"),
        "total_token_usage": state.get("total_token_usage"),
        "token_budget": state.get("token_budget"),
        "review_issue_count": len(review.get("issues", [])) if isinstance(review, dict) else 0,
    }


def _output_summary(output: Mapping[str, Any]) -> dict[str, Any]:
    code = output.get("code")
    review = output.get("review", {})
    summary: dict[str, Any] = {
        "updated_fields": sorted(str(key) for key in output),
        "status": output.get("status"),
        "retry_count": output.get("retry_count"),
        "token_delta": output.get("total_token_usage"),
        "code_chars": len(code) if isinstance(code, str) else None,
        "budget_message_present": bool(output.get("budget_message")),
    }
    if isinstance(review, dict):
        summary["review_approved"] = review.get("approved")
        summary["review_issue_count"] = len(review.get("issues", []))
        summary["review_summary_chars"] = len(str(review.get("summary", "")))
    history = output.get("history", [])
    if isinstance(history, list):
        summary["history_event_count"] = len(history)
    return summary


def _append_trace(event: dict[str, Any]) -> None:
    try:
        encoded = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with _TRACE_LOCK:
            with TRACE_PATH.open("a", encoding="utf-8") as trace_file:
                trace_file.write(encoded + "\n")
    except OSError:
        # Trace 写盘失败不能让业务图整体失败。
        return


def trace_node(agent: str) -> Callable[[Node], Node]:
    """记录节点摘要、耗时和 Token 增量，不写入任务正文或生成代码。"""

    def decorate(node: Node) -> Node:
        @wraps(node)
        def wrapped(state: Mapping[str, Any]) -> dict[str, Any]:
            started = time.perf_counter()
            input_data = _input_summary(state)
            output_data: dict[str, Any] = {}
            error_type: str | None = None
            try:
                result = node(state)
                output_data = _output_summary(result)
                return result
            except Exception as exc:
                error_type = type(exc).__name__
                raise
            finally:
                event = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent": agent,
                    "input_summary": input_data,
                    "output_summary": output_data,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                }
                if error_type:
                    event["error_type"] = error_type
                _append_trace(event)

        return wrapped  # type: ignore[return-value]

    return decorate
