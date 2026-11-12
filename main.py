import argparse
import json
import sys
from typing import Any


def _text(profile: dict[str, Any], field: str, default: str = "Not provided") -> str:
    value = str(profile.get(field, "")).strip()
    return value or default


def _number(profile: dict[str, Any], field: str, default: int) -> int:
    value = str(profile.get(field, "")).strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Student field {field!r} must be a whole number; got {value!r}.") from exc


def _parse_codes(value: str) -> list[str]:
    return [" ".join(code.strip().upper().split()) for code in value.split(",") if code.strip()]


def _course_text(row) -> str:
    code = f"{row['Subject']} {row['Number']}".strip()
    return (
        f"{code} | {row['Name']} | {row['Credit Hours']} | "
        f"Prerequisites: {row['Prerequisites'] or 'none listed'} | "
        f"Requirement group: {row['Requirement Group'] or 'not specified'}"
    )


def _build_inputs(profile: dict[str, Any], course_catalog) -> dict[str, Any]:
    required_courses = _text(profile, "remaining_required_courses", "")
    required_rows = []
    for code in _parse_codes(required_courses):
        parts = code.split(maxsplit=1)
        if len(parts) != 2:
            required_rows.append(f"{code}: invalid course-code format")
            continue
        subject, number = parts
        matches = course_catalog[
            course_catalog["Subject"].astype(str).str.strip().str.upper().eq(subject)
            & course_catalog["Number"].astype(str).str.strip().str.upper().eq(number)
            ]
        if matches.empty:
            required_rows.append(f"{code}: not found in the supplied course CSV")
        else:
            required_rows.append(_course_text(matches.iloc[0]))

    candidates = "\n".join(_course_text(row) for _, row in course_catalog.iterrows())
    return {
        "intended_semester": _text(profile, "intended_semester"),
        "major": _text(profile, "major"),
        "catalog_year": _text(profile, "catalog_year"),
        "preferences": _text(profile, "preferences"),
        "completed_courses": _text(profile, "completed_courses", ""),
        "current_courses": _text(profile, "current_courses", ""),
        "failed_courses": _text(profile, "failed_courses", ""),
        "required_courses": required_courses or "None supplied",
        "remaining_choice_groups": _text(profile, "remaining_choice_groups", "None supplied"),
        "min_unit_load": _number(profile, "min_unit_load", 0),
        "unit_limit": _number(profile, "unit_limit", 18),
        "required_course_catalog": "\n".join(required_rows) or "No required course codes supplied.",
        "course_candidates": candidates or "No non-synthetic course rows were found.",
        "revision_feedback": "No earlier validation attempt.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a preliminary graduation plan from the local student and course CSV files."
    )
    parser.add_argument(
        "--student-id",
        help="Student profile ID. If there is only one profile in the CSV, it is selected automatically.",
    )
    args = parser.parse_args(argv)

    try:
        from student_inputs import load_student
        try:
            from tools.course_tools import course_catalog
        except ModuleNotFoundError:
            from tools.course_tools import course_catalog

        profile = load_student(args.student_id)
        inputs = _build_inputs(profile, course_catalog)
    except Exception as exc:
        print(f"Could not load planning inputs: {exc}", file=sys.stderr)
        return 1

    try:
        from workflow import planning_crew
    except ModuleNotFoundError as exc:
        missing = exc.name or "a required package"
        print(f"The planner cannot start because {missing!r} is not installed.", file=sys.stderr)
        print("Install the project dependencies with: pip install -r requirements.txt", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"The planner could not be initialized: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Creating a preliminary plan for {_text(profile, 'intended_semester')}...")
    try:
        result = planning_crew.kickoff(inputs=inputs)
    except Exception as exc:
        print(f"Planning failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "Check that Ollama is running and that the configured llama3.2 model is installed.",
            file=sys.stderr,
        )
        return 1

    plan = getattr(result, "pydantic", None)
    if plan is None:
        print("The model returned no structured GraduationPlan. Raw result:")
        print(result)
        return 1

    if hasattr(plan, "model_dump"):
        plan_data = plan.model_dump()
    elif hasattr(plan, "dict"):
        plan_data = plan.dict()
    else:
        plan_data = plan

    print("\n===== PRELIMINARY GRADUATION PLAN =====\n")
    print(json.dumps(plan_data, indent=2, ensure_ascii=False, default=str))

    try:
        from validation import validate_plan

        report = validate_plan(
            plan=plan,
            min_unit_load=inputs["min_unit_load"],
            unit_limit=inputs["unit_limit"],
            required_courses=inputs["required_courses"],
            completed_courses=inputs["completed_courses"],
            current_courses=inputs["current_courses"],
        )
    except Exception as exc:
        print(f"\nPlan validation could not run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    status = "PASS" if report["passed"] else "REVIEW NEEDED"
    print(f"\n===== PYTHON VALIDATION: {status} =====")
    print(f"Planned credits: {report['planned_credit_hours']}")
    for issue in report["issues"]:
        print(f"- {issue}")
    for limitation in report["limitations"]:
        print(f"Note: {limitation}")

    return 0 if report["passed"] else 1


if __name__ == "__main__": # Every Python file has the __name__ variable
    sys.exit(main()) # End the program with this code, helps with bug fixing
