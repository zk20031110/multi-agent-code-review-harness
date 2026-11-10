from __future__ import annotations

from pathlib import Path

from tools.rag import StandardsRAG


def test_rag_indexes_and_retrieves_standards(tmp_path: Path) -> None:
    standards_dir = tmp_path / "standards"
    standards_dir.mkdir()
    (standards_dir / "python_style.md").write_text(
        "# Python tests\n\n"
        "Add regression tests for bug fixes. Validate empty inputs and boundaries.\n",
        encoding="utf-8",
    )
    (standards_dir / "security.md").write_text(
        "# Security\n\nDo not log API keys or secrets.\n",
        encoding="utf-8",
    )

    rag = StandardsRAG(
        standards_dir=standards_dir,
        chroma_dir=tmp_path / "chroma",
    )
    indexed = rag.index_standards()
    matches = rag.search("regression tests for bug fixes", limit=2)

    assert indexed >= 2
    assert matches
    assert "regression tests" in matches[0]["text"]
