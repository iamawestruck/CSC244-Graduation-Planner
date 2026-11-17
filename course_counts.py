"""Course-count helpers: how many courses does the semester plan need?

Uses SQL (SQLite in memory, part of the Python standard library) to count the
remaining required courses by department, and compares a plan's size with
either a department-selected target or the number of courses implied by the
semester's unit range.

Run from the project root:
    python course_counts.py --student-id SYNTHETIC_001
    python course_counts.py --student-id SYNTHETIC_001 --dept-target 5
"""
import argparse
import math
import sqlite3
import sys

import pandas as pd

DEFAULT_TYPICAL_UNITS = 3  # most catalog courses are 3 units


def normalize_code(code: str) -> str:
    return " ".join(str(code).strip().upper().split())


def parse_codes(value: str) -> list[str]:
    """'csc 130, CSC  131' -> ['CSC 130', 'CSC 131'] (order kept, duplicates removed)."""
    codes = []
    for part in str(value or "").split(","):
        code = normalize_code(part)
        if code and code not in codes:
            codes.append(code)
    return codes


def build_catalog_db(course_catalog: pd.DataFrame) -> sqlite3.Connection:
    """Load the catalog into an in-memory SQL table with one row per course code."""
    conn = sqlite3.connect(":memory:")
    course_catalog[["Subject", "Number", "Credit Hours"]].to_sql("catalog_raw", conn, index=False)
    conn.execute(
        """
        CREATE TABLE catalog AS
        SELECT UPPER(TRIM("Subject")) || ' ' || UPPER(TRIM("Number")) AS code,
               MIN(UPPER(TRIM("Subject")))                            AS department,
               MIN("Credit Hours")                                    AS credit_hours
        FROM catalog_raw
        GROUP BY code
        """
    )
    return conn


def count_remaining_required(
        conn: sqlite3.Connection,
        required_codes: list[str],
        completed_codes: list[str],
) -> dict:
    """Count required courses the student has not completed yet, by department."""
    for table in ("required", "completed"):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(f"CREATE TABLE {table} (code TEXT)")
    conn.executemany("INSERT INTO required VALUES (?)", [(c,) for c in required_codes])
    conn.executemany("INSERT INTO completed VALUES (?)", [(c,) for c in completed_codes])

    by_department = dict(conn.execute(
        """
        SELECT c.department, COUNT(*)
        FROM required r
        JOIN catalog c ON c.code = r.code
        WHERE r.code NOT IN (SELECT code FROM completed)
        GROUP BY c.department
        ORDER BY c.department
        """
    ))
    missing = [row[0] for row in conn.execute(
        """
        SELECT r.code
        FROM required r
        LEFT JOIN catalog c ON c.code = r.code
        WHERE c.code IS NULL
        ORDER BY r.code
        """
    )]
    return {
        "remaining_required_total": sum(by_department.values()),
        "by_department": by_department,
        "missing_from_catalog": missing,
    }


def course_count_range(
        min_units: int,
        max_units: int,
        typical_units: int = DEFAULT_TYPICAL_UNITS,
) -> tuple[int, int]:
    """Approximate number of courses that fit the unit range, e.g. 12-18 units -> (4, 6)."""
    if typical_units <= 0:
        raise ValueError("typical_units must be positive.")
    if min_units < 0 or max_units < min_units:
        raise ValueError("Unit range must satisfy 0 <= min_units <= max_units.")
    low = math.ceil(min_units / typical_units)
    high = max(low, max_units // typical_units)
    return low, high


def course_count_issues(
        planned_count: int,
        min_units: int,
        max_units: int,
        dept_target: int | None = None,
        typical_units: int = DEFAULT_TYPICAL_UNITS,
) -> list[str]:
    """Compare the number of planned courses with the department target, or the unit range."""
    if dept_target is not None:
        if dept_target <= 0:
            raise ValueError("dept_target must be a positive whole number.")
        if planned_count != dept_target:
            return [
                f"Plan has {planned_count} courses; the department-selected count is {dept_target}."
            ]
        return []

    low, high = course_count_range(min_units, max_units, typical_units)
    if planned_count < low:
        return [
            f"Plan has {planned_count} courses; about {low} to {high} are expected "
            f"for {min_units}-{max_units} units."
        ]
    if planned_count > high:
        return [
            f"Plan has {planned_count} courses; about {low} to {high} are expected "
            f"for {min_units}-{max_units} units."
        ]
    return []


def summarize_course_counts(
        course_catalog: pd.DataFrame,
        required_courses: str,
        completed_courses: str,
        min_units: int,
        max_units: int,
        dept_target: int | None = None,
        typical_units: int = DEFAULT_TYPICAL_UNITS,
) -> dict:
    conn = build_catalog_db(course_catalog)
    try:
        summary = count_remaining_required(
            conn, parse_codes(required_courses), parse_codes(completed_courses)
        )
    finally:
        conn.close()

    low, high = course_count_range(min_units, max_units, typical_units)
    summary["unit_range_course_count"] = {"min": low, "max": high}
    summary["dept_target"] = dept_target
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Count the courses needed for the semester plan.")
    parser.add_argument("--student-id", help="Student profile ID (optional if the CSV has one profile).")
    parser.add_argument("--dept-target", type=int,
                        help="Number of courses the department selected for the semester.")
    args = parser.parse_args(argv)

    # Imported here so the helpers above can be used (and tested) without these modules.
    from student_inputs import load_student
    from tools.course_tools import course_catalog

    try:
        profile = load_student(args.student_id)
    except ValueError as exc:
        print(f"Could not load the student profile: {exc}", file=sys.stderr)
        return 1
    min_units = int(profile["min_unit_load"])
    max_units = int(profile["max_unit_load"])
    summary = summarize_course_counts(
        course_catalog,
        profile["remaining_required_courses"],
        profile["completed_courses"],
        min_units,
        max_units,
        args.dept_target,
    )

    print(f"Remaining required courses: {summary['remaining_required_total']}")
    for department, count in summary["by_department"].items():
        print(f"  {department}: {count}")
    rng = summary["unit_range_course_count"]
    print(f"Courses for {min_units}-{max_units} units (at {DEFAULT_TYPICAL_UNITS} units each): "
          f"{rng['min']} to {rng['max']}")
    if args.dept_target is not None:
        print(f"Department-selected count: {args.dept_target}")
    if summary["missing_from_catalog"]:
        print("Not found in the catalog: " + ", ".join(summary["missing_from_catalog"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
