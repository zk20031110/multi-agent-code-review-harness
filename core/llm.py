from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


ROOT_DIR = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT_DIR / "prompts"


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    base_url: str
    model: str


def load_settings() -> LLMSettings:
    load_dotenv(ROOT_DIR / ".env")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not api_key or not base_url or not model:
        raise ValueError(
            "请在 .env 中配置 OPENAI_API_KEY、OPENAI_BASE_URL 和 OPENAI_MODEL"
        )
    return LLMSettings(api_key=api_key, base_url=base_url, model=model)


def create_chat_model(settings: LLMSettings | None = None) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    config = settings or load_settings()
    return ChatOpenAI(
        model=config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0,
        timeout=60,
        max_retries=2,
        use_responses_api=False,
    )


def render_prompt(name: str, values: dict[str, str]) -> str:
    template = (PROMPT_DIR / name).read_text(encoding="utf-8")
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def invoke_text(
    model: BaseChatModel,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, int]:
    message = model.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    content: Any = message.content
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict)
        )
    else:
        text = str(content)

    usage = getattr(message, "usage_metadata", None) or {}
    token_total = usage.get("total_tokens", 0)
    if not token_total:
        metadata = getattr(message, "response_metadata", {}) or {}
        token_total = (metadata.get("token_usage") or {}).get("total_tokens", 0)
    return text, int(token_total or 0)


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("模型响应的 JSON 顶层必须是对象")
    return value
