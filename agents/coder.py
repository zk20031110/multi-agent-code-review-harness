from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from core.llm import invoke_text, parse_json_object, render_prompt
from core.schemas import CoderOutput
from core.state import ReviewState


class Coder:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    def __call__(self, state: ReviewState) -> dict[str, Any]:
        tokens = 0
        review = state["review"]
        feedback = "\n".join([
            review.get("summary", ""),
            *review.get("issues", []),
            *review.get("suggestions", []),
        ]) or "这是第一轮编码，尚无审查反馈。"
        prompt = render_prompt("coder.md", {
            "task": state["task"],
            "plan_json": json.dumps(state["plan"], ensure_ascii=False, indent=2),
            "current_code": state["code"] or "暂无已有代码。",
            "review_feedback": feedback,
            "style_context": review.get("rag_context", "暂无检索结果。"),
            "memory_context": state["memory_context"] or "暂无历史修复记录。",
        })
        try:
            response, tokens = invoke_text(
                self.model, "你是谨慎的代码生成 Agent。严格遵守输出契约。", prompt
            )
            result = CoderOutput.model_validate(parse_json_object(response))
            files = {item.path: item.content for item in result.files}

            return {
                "code": json.dumps(files, ensure_ascii=False),
                "status": "coding",
                "total_token_usage": tokens,
                "history": [{
                    "agent": "coder",
                    "summary": result.summary[:500],
                }],
            }
        except ValidationError as exc:
            details = []
            for issue in exc.errors(include_input=False, include_context=False)[:8]:
                location = ".".join(str(part) for part in issue.get("loc", ()))
                details.append(f"{location or 'output'}: {issue.get('msg', '校验失败')}")
            return self._retry_with_feedback(
                state,
                "Coder 输出未通过 Pydantic 校验：" + "；".join(details),
                tokens,
            )
        except Exception as exc:
            return self._retry_with_feedback(
                state,
                f"Coder 模型调用或 JSON 解析失败（{type(exc).__name__}）；请按完整 JSON 契约重新生成。",
                tokens,
            )

    @staticmethod
    def _retry_with_feedback(
        state: ReviewState,
        message: str,
        tokens: int,
    ) -> dict[str, Any]:
        review = dict(state["review"])
        review.update({
            "approved": False,
            "summary": "Coder 输出校验失败，等待重新生成。",
            "issues": [message[:1500]],
            "suggestions": [
                "重新输出完整 JSON；确保每个 Python 文件语法有效、路径安全，并包含 pytest 文件。"
            ],
            "test_output": "",
        })
        retry_count = state["retry_count"] + 1
        return {
            "review": review,
            "status": "coder_error",
            "retry_count": retry_count,
            "total_token_usage": tokens,
            "history": [{
                "agent": "coder",
                "summary": f"输出校验失败，已请求重新生成；返工计数={retry_count}。",
            }],
        }
