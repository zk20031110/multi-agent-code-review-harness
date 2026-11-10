from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class FakeMessage:
    content: str
    usage_metadata: dict[str, int]


class FakeModel:
    """离线测试用模型桩，不代表真实模型表现或 Token 消耗。"""

    def __init__(self, responses: list[str], repeat_last: bool = False) -> None:
        if not responses:
            raise ValueError("responses 不能为空")
        self.responses = responses
        self.repeat_last = repeat_last
        self.index = 0

    def invoke(self, messages: Sequence[Any]) -> FakeMessage:
        if self.index < len(self.responses):
            response = self.responses[self.index]
            self.index += 1
        elif self.repeat_last:
            response = self.responses[-1]
        else:
            raise AssertionError("FakeModel 没有更多预置响应")
        return FakeMessage(response, {"total_tokens": 0})


class FakeRAG:
    def search(self, query: str, limit: int = 4) -> list[dict[str, str | float]]:
        return []
