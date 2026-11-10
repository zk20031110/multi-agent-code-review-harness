from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from core.llm import invoke_text, parse_json_object, render_prompt
from core.state import ReviewState
from tools.code_runner import run_project
from tools.rag import StandardsRAG


class Reviewer:
    def __init__(
        self,
        model: BaseChatModel,
        rag: StandardsRAG,
        timeout_seconds: int = 15,
    ) -> None:
        self.model = model
        self.rag = rag
        self.timeout_seconds = timeout_seconds

    def __call__(self, state: ReviewState) -> dict[str, Any]:
        code_parse_error = ""
        try:
            files = json.loads(state["code"]) if state["code"] else {}
            if not isinstance(files, dict):
                raise ValueError("code 字段不是文件映射 JSON")
            project_files = {str(path): str(text) for path, text in files.items()}
        except Exception as exc:
            project_files = {}
            code_parse_error = f"代码包解析失败：{type(exc).__name__}: {exc}"

        rag_error = ""
        try:
            retrieved = self.rag.search(state["task"] + "\n" + state["code"], limit=4)
            rag_context = "\n\n".join(
                f"[来源：{item['source']}]\n{item['text']}" for item in retrieved
            ) or "未检索到代码规范片段。"
        except Exception as exc:
            rag_context = "RAG 检索不可用。"
            rag_error = f"规范检索失败：{type(exc).__name__}"

        test_result = run_project(project_files, timeout_seconds=self.timeout_seconds)
        prompt = render_prompt("reviewer.md", {
            "task": state["task"],
            "plan_json": json.dumps(state["plan"], ensure_ascii=False, indent=2),
            "code": state["code"] or "没有生成代码。",
            "test_output": (
                f"状态：{test_result['status']}\n模式：{test_result['mode']}\n"
                f"退出码：{test_result['return_code']}\n输出：\n{test_result['output']}\n"
                f"{code_parse_error}\n{rag_error}"
            ),
            "style_context": rag_context,
        })

        tokens = 0
        try:
            response, tokens = invoke_text(
                self.model, "你是谨慎的代码审查 Agent，测试事实优先于主观判断。", prompt
            )
            verdict = parse_json_object(response)
        except Exception as exc:
            verdict = {
                "approved": False,
                "summary": "Reviewer 模型调用或响应解析失败。",
                "issues": [f"Reviewer 错误类型：{type(exc).__name__}"],
                "suggestions": [],
            }

        issues = [str(item) for item in verdict.get("issues", [])]
        suggestions = [str(item) for item in verdict.get("suggestions", [])]
        if code_parse_error:
            issues.append(code_parse_error)
        if rag_error:
            suggestions.append(rag_error)
        if test_result["status"] != "passed":
            issues.append(
                "pytest 未通过或未运行；"
                f"状态={test_result['status']}，模式={test_result['mode']}。"
            )

        approved = (
            bool(verdict.get("approved", False))
            and test_result["status"] == "passed"
            and test_result["mode"] == "pytest"
            and not code_parse_error
        )
        retry_count = state["retry_count"] + (0 if approved else 1)
        review = {
            "approved": approved,
            "summary": str(verdict.get("summary", "审查完成。"))[:1000],
            "issues": issues,
            "suggestions": suggestions,
            "test_output": test_result["output"][:10_000],
            "rag_context": rag_context[:10_000],
        }
        return {
            "review": review,
            "retry_count": retry_count,
            "status": "approved" if approved else "needs_revision",
            "total_token_usage": tokens,
            "history": [{
                "agent": "reviewer",
                "summary": (
                    f"{'通过' if approved else '未通过'}；测试={test_result['status']}；"
                    f"重试计数={retry_count}。"
                ),
            }],
        }
