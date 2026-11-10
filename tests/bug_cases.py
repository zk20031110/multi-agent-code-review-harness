from __future__ import annotations

from typing import TypedDict

from tests.weighted_route_case import WEIGHTED_ROUTE_CASE


class BugCase(TypedDict):
    name: str
    task: str
    buggy_files: dict[str, str]
    fixed_files: dict[str, str]


BUG_CASES: list[BugCase] = [
    {
        "name": "clamp_bounds",
        "task": "修复 clamp 函数的上下界处理错误，让返回值位于 lower 和 upper 之间。",
        "buggy_files": {
            "solution.py": "def clamp(value, lower, upper):\n    return max(upper, min(lower, value))\n",
            "test_clamp.py": (
                "from solution import clamp\n\n"
                "def test_clamp_inside_range():\n    assert clamp(5, 0, 10) == 5\n\n"
                "def test_clamp_below_range():\n    assert clamp(-2, 0, 10) == 0\n\n"
                "def test_clamp_above_range():\n    assert clamp(12, 0, 10) == 10\n"
            ),
        },
        "fixed_files": {
            "solution.py": "def clamp(value, lower, upper):\n    return max(lower, min(upper, value))\n",
            "test_clamp.py": (
                "from solution import clamp\n\n"
                "def test_clamp_inside_range():\n    assert clamp(5, 0, 10) == 5\n\n"
                "def test_clamp_below_range():\n    assert clamp(-2, 0, 10) == 0\n\n"
                "def test_clamp_above_range():\n    assert clamp(12, 0, 10) == 10\n"
            ),
        },
    },
    {
        "name": "safe_divide",
        "task": "修复 safe_divide：除数为 0 时返回 0，否则返回正常商。",
        "buggy_files": {
            "solution.py": (
                "def safe_divide(numerator, denominator):\n"
                "    if denominator == 0:\n        return numerator\n"
                "    return numerator / denominator\n"
            ),
            "test_divide.py": (
                "from solution import safe_divide\n\n"
                "def test_regular_division():\n    assert safe_divide(8, 2) == 4\n\n"
                "def test_zero_denominator():\n    assert safe_divide(8, 0) == 0\n"
            ),
        },
        "fixed_files": {
            "solution.py": (
                "def safe_divide(numerator, denominator):\n"
                "    if denominator == 0:\n        return 0\n"
                "    return numerator / denominator\n"
            ),
            "test_divide.py": (
                "from solution import safe_divide\n\n"
                "def test_regular_division():\n    assert safe_divide(8, 2) == 4\n\n"
                "def test_zero_denominator():\n    assert safe_divide(8, 0) == 0\n"
            ),
        },
    },
    {
        "name": "average_precision",
        "task": "修复 average：返回精确平均值，不能截断小数部分；空列表抛出 ValueError。",
        "buggy_files": {
            "solution.py": (
                "def average(values):\n"
                "    if not values:\n        raise ValueError('values cannot be empty')\n"
                "    return sum(values) // len(values)\n"
            ),
            "test_average.py": (
                "import pytest\nfrom solution import average\n\n"
                "def test_average_keeps_fraction():\n    assert average([2, 3]) == 2.5\n\n"
                "def test_empty_input_raises():\n"
                "    with pytest.raises(ValueError):\n        average([])\n"
            ),
        },
        "fixed_files": {
            "solution.py": (
                "def average(values):\n"
                "    if not values:\n        raise ValueError('values cannot be empty')\n"
                "    return sum(values) / len(values)\n"
            ),
            "test_average.py": (
                "import pytest\nfrom solution import average\n\n"
                "def test_average_keeps_fraction():\n    assert average([2, 3]) == 2.5\n\n"
                "def test_empty_input_raises():\n"
                "    with pytest.raises(ValueError):\n        average([])\n"
            ),
        },
    },
    {
        "name": "normalize_name",
        "task": "修复 normalize_name：清除首尾空白并转成小写。",
        "buggy_files": {
            "solution.py": "def normalize_name(name):\n    return name.lower()\n",
            "test_name.py": (
                "from solution import normalize_name\n\n"
                "def test_name_is_trimmed_and_lowercase():\n"
                "    assert normalize_name('  Alice Smith  ') == 'alice smith'\n"
            ),
        },
        "fixed_files": {
            "solution.py": "def normalize_name(name):\n    return name.strip().lower()\n",
            "test_name.py": (
                "from solution import normalize_name\n\n"
                "def test_name_is_trimmed_and_lowercase():\n"
                "    assert normalize_name('  Alice Smith  ') == 'alice smith'\n"
            ),
        },
    },
    {
        "name": "stable_dedupe",
        "task": "修复 dedupe_preserve_order：去重时保留元素首次出现顺序。",
        "buggy_files": {
            "solution.py": "def dedupe_preserve_order(values):\n    return sorted(set(values))\n",
            "test_dedupe.py": (
                "from solution import dedupe_preserve_order\n\n"
                "def test_dedupe_keeps_first_occurrence_order():\n"
                "    assert dedupe_preserve_order([3, 1, 3, 2, 1]) == [3, 1, 2]\n"
            ),
        },
        "fixed_files": {
            "solution.py": "def dedupe_preserve_order(values):\n    return list(dict.fromkeys(values))\n",
            "test_dedupe.py": (
                "from solution import dedupe_preserve_order\n\n"
                "def test_dedupe_keeps_first_occurrence_order():\n"
                "    assert dedupe_preserve_order([3, 1, 3, 2, 1]) == [3, 1, 2]\n"
            ),
        },
    },
]

BUG_CASES.append(WEIGHTED_ROUTE_CASE)
