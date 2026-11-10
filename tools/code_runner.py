from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import TypedDict


MAX_FILES = 40
MAX_FILE_BYTES = 200_000
MAX_TOTAL_BYTES = 1_000_000
MAX_OUTPUT_CHARS = 20_000
ALLOWED_SUFFIXES = {".py", ".txt", ".md", ".toml", ".ini"}
PROJECT_DIR = Path(__file__).resolve().parents[1]
RUNNER_TEMP_DIR = PROJECT_DIR / "storage" / "runner_tmp"


class RunResult(TypedDict):
    status: str
    mode: str
    return_code: int | None
    output: str


def _validate_files(files: dict[str, str]) -> dict[str, str]:
    if not files:
        raise ValueError("没有可执行的文件")
    if len(files) > MAX_FILES:
        raise ValueError(f"文件数量超过限制：{MAX_FILES}")

    clean_files: dict[str, str] = {}
    total_bytes = 0
    for raw_path, content in files.items():
        normalized = raw_path.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts or ":" in normalized:
            raise ValueError(f"非法文件路径：{raw_path}")
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValueError(f"不允许的文件类型：{raw_path}")
        if not isinstance(content, str):
            raise ValueError(f"文件内容必须是字符串：{raw_path}")
        size = len(content.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            raise ValueError(f"单文件超过大小限制：{raw_path}")
        total_bytes += size
        clean_files[str(path)] = content

    if total_bytes > MAX_TOTAL_BYTES:
        raise ValueError("所有生成文件的总大小超过限制")
    return clean_files


def run_project(files: dict[str, str], timeout_seconds: int = 15) -> RunResult:
    """pytest 在临时目录运行；没有测试时只编译语法，不执行代码。"""
    try:
        safe_files = _validate_files(files)
    except Exception as exc:
        return {
            "status": "error",
            "mode": "validation",
            "return_code": None,
            "output": f"文件校验失败：{type(exc).__name__}: {exc}",
        }

    has_tests = any(
        (Path(name).name.startswith("test_") or Path(name).name.endswith("_test.py"))
        and name.endswith(".py")
        for name in safe_files
    )
    mode = "pytest" if has_tests else "compile"

    RUNNER_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="agent-review-",
        dir=RUNNER_TEMP_DIR,
    ) as temp_dir:
        root = Path(temp_dir).resolve()
        try:
            for relative_path, content in safe_files.items():
                destination = (root / relative_path).resolve()
                destination.relative_to(root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")

            if has_tests:
                command = [
                    sys.executable,
                    "-I",
                    "-c",
                    "import sys; sys.path.insert(0, '.'); import pytest; "
                    "raise SystemExit(pytest.main(['-q', '--disable-warnings', '--maxfail=1']))",
                ]
            else:
                command = [sys.executable, "-I", "-m", "compileall", "-q", "."]

            env = {
                key: os.environ[key]
                for key in ("PATH", "SYSTEMROOT", "WINDIR")
                if key in os.environ
            }
            env["TEMP"] = str(RUNNER_TEMP_DIR)
            env["TMP"] = str(RUNNER_TEMP_DIR)
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

            completed = subprocess.run(
                command,
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=max(1, timeout_seconds),
                shell=False,
                check=False,
            )
            output = ((completed.stdout or "") + (completed.stderr or ""))[-MAX_OUTPUT_CHARS:]
            if completed.returncode == 0 and has_tests:
                status = "passed"
            elif completed.returncode == 0:
                status = "no_tests"
            else:
                status = "failed"
            return {
                "status": status,
                "mode": mode,
                "return_code": completed.returncode,
                "output": output or "命令已结束，没有输出。",
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "timeout",
                "mode": mode,
                "return_code": None,
                "output": f"执行超过 {timeout_seconds} 秒，已终止。{exc.stdout or ''}{exc.stderr or ''}",
            }
        except Exception as exc:
            return {
                "status": "error",
                "mode": mode,
                "return_code": None,
                "output": f"执行失败：{type(exc).__name__}: {exc}",
            }
