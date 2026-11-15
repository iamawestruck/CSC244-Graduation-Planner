import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from course_counts import (
    course_count_issues,
    course_count_range,
    parse_codes,
    summarize_course_counts,
)


def make_catalog(*codes):
    return pd.DataFrame({
        "Subject": [c.split()[0] for c in codes],
        "Number": [c.split()[1] for c in codes],
        "Credit Hours": ["3 hours."] * len(codes),
    })


CATALOG = make_catalog("CSC 60", "CSC 130", "CSC 131", "MATH 30")


def summarize(required, completed="", min_units=12, max_units=18, catalog=CATALOG, dept_target=None):
    return summarize_course_counts(catalog, required, completed, min_units, max_units, dept_target)


def test_parse_codes_normalizes_and_dedupes():
    assert parse_codes(" csc  130, CSC 130 ,Math 30,,") == ["CSC 130", "MATH 30"]


def test_counts_by_department_and_skips_completed():
    result = summarize("CSC 60, CSC 130, MATH 30", completed="CSC 60")
    assert result["by_department"] == {"CSC": 1, "MATH": 1}
    assert result["remaining_required_total"] == 2


def test_lowercase_and_extra_spaces_still_match():
    assert summarize("csc   130")["remaining_required_total"] == 1


def test_course_not_in_catalog_is_reported_not_counted():
    result = summarize("CSC 130, CSC 999")
    assert result["remaining_required_total"] == 1
    assert result["missing_from_catalog"] == ["CSC 999"]


def test_repeated_required_course_counted_once():
    assert summarize("CSC 130, CSC 130")["remaining_required_total"] == 1


def test_duplicate_catalog_rows_are_not_double_counted():
    catalog = make_catalog("CSC 130", "CSC 130", "CSC 60")
    assert summarize("CSC 130, CSC 60", catalog=catalog)["remaining_required_total"] == 2


def test_nothing_required_gives_zero():
    result = summarize("")
    assert result["remaining_required_total"] == 0 and result["by_department"] == {}


def test_course_count_range():
    assert course_count_range(12, 18) == (4, 6)
    assert course_count_range(9, 9) == (3, 3)
    assert course_count_range(12, 18, typical_units=4) == (3, 4)


@pytest.mark.parametrize("args", [(-1, 12), (18, 12)])
def test_course_count_range_rejects_bad_units(args):
    with pytest.raises(ValueError):
        course_count_range(*args)


def test_issues_use_unit_range_when_no_department_target():
    assert course_count_issues(4, 12, 18) == []
    assert course_count_issues(6, 12, 18) == []
    assert "3 courses" in course_count_issues(3, 12, 18)[0]
    assert "7 courses" in course_count_issues(7, 12, 18)[0]


def test_department_target_overrides_unit_range():
    assert course_count_issues(5, 12, 18, dept_target=5) == []
    issues = course_count_issues(4, 12, 18, dept_target=5)
    assert len(issues) == 1 and "department-selected count is 5" in issues[0]


def test_department_target_must_be_positive():
    with pytest.raises(ValueError):
        course_count_issues(4, 12, 18, dept_target=0)


def test_real_catalog_and_sample_student():
    """Numbers for SYNTHETIC_001 in the project's own CSV files."""
    courses = pd.read_csv(ROOT / "data" / "sac_state_courses.csv", dtype=str, keep_default_na=False)
    catalog = courses[courses["Section Status"].str.strip().str.upper() != "SYNTHETIC - NOT REAL"]
    student = pd.read_csv(ROOT / "data" / "sac_state_students.csv", dtype=str, keep_default_na=False).iloc[0]
    result = summarize_course_counts(
        catalog, student["remaining_required_courses"], student["completed_courses"],
        int(student["min_unit_load"]), int(student["max_unit_load"]),
    )
    assert result["remaining_required_total"] == 12
    assert result["by_department"] == {"CSC": 11, "PHIL": 1}
    assert result["missing_from_catalog"] == []
    assert result["unit_range_course_count"] == {"min": 4, "max": 6}
