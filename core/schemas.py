from __future__ import annotations

import ast
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ALLOWED_SUFFIXES = {".py", ".txt", ".md", ".toml", ".ini"}
MAX_FILES = 40


class CoderFile(BaseModel):
    """Coder 返回的单个文件；Python 文件在进入执行器前先做语法校验。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    path: str = Field(min_length=1)
    content: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def validate_path(cls, raw_path: str) -> str:
        normalized = raw_path.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts or ":" in normalized:
            raise ValueError("path 必须是安全的相对路径")
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValueError("文件扩展名不在允许列表中")
        return str(path)

    @model_validator(mode="after")
    def validate_python_syntax(self) -> CoderFile:
        if self.path.lower().endswith(".py"):
            try:
                ast.parse(self.content, filename=self.path)
            except SyntaxError as exc:
                line = exc.lineno or 0
                column = exc.offset or 0
                message = exc.msg or "语法错误"
                raise ValueError(
                    f"Python 语法错误（第 {line} 行，第 {column} 列）：{message}"
                ) from exc
        return self


class CoderOutput(BaseModel):
    """Coder 的结构化输出契约。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    summary: str = Field(min_length=1, max_length=1000)
    files: list[CoderFile] = Field(min_length=1, max_length=MAX_FILES)

    @model_validator(mode="after")
    def validate_file_set(self) -> CoderOutput:
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("files 中不能包含重复路径")

        has_test_file = any(
            PurePosixPath(path).name.startswith("test_")
            or PurePosixPath(path).name.endswith("_test.py")
            for path in paths
            if path.lower().endswith(".py")
        )
        if not has_test_file:
            raise ValueError("files 必须包含至少一个 pytest 测试文件")
        return self
