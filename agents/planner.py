from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from core.llm import invoke_text, parse_json_object, render_prompt
from core.state import ReviewState


class Planner:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    def __call__(self, state: ReviewState) -> dict[str, Any]:
        tokens = 0
        prompt = render_prompt("planner.md", {
            "task": state["task"],
            "memory_context": state["memory_context"] or "暂无历史修复记录。",
        })
        try:
            response, tokens = invoke_text(
                self.model, "你是严谨的软件研发任务规划 Agent。", prompt
            )
            result = parse_json_object(response)
            plan = [f"目标：{result.get('goal', state['task'])}"]
            plan.extend(f"步骤：{item}" for item in result.get("steps", []))
            plan.extend(
                f"验收标准：{item}"
                for item in result.get("acceptance_criteria", [])
            )
            plan.extend(f"假设：{item}" for item in result.get("assumptions", []))
            plan.extend(f"风险：{item}" for item in result.get("risks", []))
            return {
                "plan": plan,
                "status": "planned",
                "total_token_usage": tokens,
                "history": [{"agent": "planner", "summary": f"形成 {len(plan)} 条任务说明。"}],
            }
        except Exception as exc:
            return {
                "plan": [f"目标：{state['task']}", "规划服务异常，请谨慎检查任务边界。"],
                "status": "degraded",
                "total_token_usage": tokens,
                "history": [{
                    "agent": "planner",
                    "summary": f"规划失败，错误类型：{type(exc).__name__}。",
                }],
            }
