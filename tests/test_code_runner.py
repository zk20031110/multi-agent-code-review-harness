from __future__ import annotations

from tools.code_runner import run_project


def test_runner_passes_valid_pytest_project() -> None:
    result = run_project({
        "solution.py": "def add(a, b):\n    return a + b\n",
        "test_add.py": "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    })
    assert result["status"] == "passed"
    assert result["mode"] == "pytest"


def test_runner_reports_failed_test() -> None:
    result = run_project({
        "solution.py": "def add(a, b):\n    return a - b\n",
        "test_add.py": "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    })
    assert result["status"] == "failed"
    assert result["return_code"] != 0


def test_runner_compiles_when_tests_are_missing() -> None:
    result = run_project({"solution.py": "def answer():\n    return 42\n"})
    assert result["status"] == "no_tests"
    assert result["mode"] == "compile"


def test_runner_rejects_path_traversal() -> None:
    result = run_project({"../outside.py": "print('no')\n"})
    assert result["status"] == "error"
    assert "非法文件路径" in result["output"]


def test_runner_rejects_unapproved_extension() -> None:
    result = run_project({"payload.exe": "not allowed"})
    assert result["status"] == "error"
    assert "不允许的文件类型" in result["output"]
