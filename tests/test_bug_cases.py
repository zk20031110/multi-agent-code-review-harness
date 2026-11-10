from __future__ import annotations

import pytest

from tests.bug_cases import BUG_CASES, BugCase
from tools.code_runner import run_project


@pytest.mark.parametrize("case", BUG_CASES, ids=lambda case: case["name"])
def test_bug_case_fails_before_fix(case: BugCase) -> None:
    result = run_project(case["buggy_files"])
    assert result["status"] == "failed"


@pytest.mark.parametrize("case", BUG_CASES, ids=lambda case: case["name"])
def test_bug_case_passes_after_fix(case: BugCase) -> None:
    result = run_project(case["fixed_files"])
    assert result["status"] == "passed"
