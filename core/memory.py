from __future__ import annotations

import re
import sqlite3
from pathlib import Path


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*|[\u4e00-\u9fff]+", text.lower()))


class SQLiteReviewMemory:
    """保存审查摘要，并用轻量词项重合度检索相似历史记录。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS review_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    issues TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )

    def remember(
        self,
        task: str,
        status: str,
        summary: str,
        issues: list[str],
    ) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT INTO review_memory (task, status, summary, issues) VALUES (?, ?, ?, ?)",
                (task, status, summary, "\n".join(issues)),
            )

    def search(self, query: str, limit: int = 3) -> str:
        query_words = _words(query)
        if not query_words:
            return ""

        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT task, status, summary, issues FROM review_memory ORDER BY id DESC LIMIT 200"
            ).fetchall()

        ranked: list[tuple[float, tuple[str, str, str, str]]] = []
        for row in rows:
            row_words = _words(" ".join(str(part) for part in row))
            score = len(query_words & row_words) / max(1, len(query_words))
            if score > 0:
                ranked.append((score, row))

        ranked.sort(key=lambda item: item[0], reverse=True)
        excerpts = [
            f"历史任务：{task}\n状态：{status}\n摘要：{summary}\n问题：{issues}"
            for _, (task, status, summary, issues) in ranked[:max(1, limit)]
        ]
        return "\n\n".join(excerpts)
