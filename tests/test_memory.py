from __future__ import annotations

from pathlib import Path

from core.memory import SQLiteReviewMemory


def test_memory_saves_and_retrieves_related_review(tmp_path: Path) -> None:
    memory = SQLiteReviewMemory(tmp_path / "memory.sqlite3")
    memory.remember(
        task="修复 Python 数据清洗函数的空值处理",
        status="needs_revision",
        summary="补充空值边界检查",
        issues=["空列表没有处理"],
    )

    result = memory.search("Python 数据清洗 空值")

    assert "空列表没有处理" in result
    assert "needs_revision" in result
