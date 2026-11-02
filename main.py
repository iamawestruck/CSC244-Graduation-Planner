from schedule import check_schedule_conflicts
from student_inputs import load_student
from validation import (
    find_catalog_course,
    parse_course_list,
    validate_plan,
)
from workflow import planning_crew

MAX_ATTEMPTS = 2
STUDENT_ID = "SYNTHETIC_001"


def build_required_course_catalog(
        required_courses: str,
        completed_courses: str,
) -> tuple[str, list[str]]:
    required = parse_course_list(required_courses)
    completed = parse_course_list(completed_courses)
    uncompleted = sorted(required - completed)

    if not uncompleted:
        return "No uncompleted required courses.", []

    details = []
    missing_codes = []

    for code in uncompleted:
        row = find_catalog_course(code)

        if row is None:
            details.append(f"{code}: NOT FOUND in the catalog.")
            missing_codes.append(code)
        else:
            details.append(
                f"{code}: FOUND. "
                f"Name: {row['Name']}. "
                f"Credit hours: {row['Credit Hours']}."
            )

    return "\n".join(details), missing_codes


student = load_student(STUDENT_ID)

base_inputs = {
    "intended_semester": student["intended_semester"],
    "major": student["major"],
    "catalog_year": student["catalog_year"],
    "preferences": student["preferences"],
    "completed_courses": student["completed_courses"],
    "current_courses": student["current_courses"],
    "failed_courses": student["failed_courses"],
    "required_courses": student["remaining_required_courses"],
    "remaining_choice_groups": student["remaining_choice_groups"],
    "min_unit_load": int(student["min_unit_load"]),
    "unit_limit": int(student["unit_limit"]),
}

(
    base_inputs["required_course_catalog"],
    missing_required_codes,
) = build_required_course_catalog(
    base_inputs["required_courses"],
    base_inputs["completed_courses"],
)

print("\n--- Required course catalog check ---")
if missing_required_codes:
    print("Not found:", ", ".join(missing_required_codes))
else:
    print("All uncompleted required courses are in the catalog.")

revision_feedback = "Create the initial semester plan."
final_plan = None
final_validation = None

for attempt in range(1, MAX_ATTEMPTS + 1):
    print(f"\n--- Planning attempt {attempt} ---")

    try:
        result = planning_crew.kickoff(
            inputs={
                **base_inputs,
                "revision_feedback": revision_feedback,
            }
        )
    except Exception as exc:
        print("\n--- Planner error ---")
        print(exc)
        final_validation = {
            "passed": False,
            "issues": [f"Planner failed: {exc}"],
        }
        break

    task_output = result.tasks_output[0] if result.tasks_output else None
    plan = task_output.pydantic if task_output else None

    if plan is None:
        issues = [
            "The planner did not return a valid GraduationPlan."
        ]
        final_validation = {
            "passed": False,
            "issues": issues,
        }
    else:
        final_plan = plan

        validation = validate_plan(
            plan=plan,
            min_unit_load=base_inputs["min_unit_load"],
            unit_limit=base_inputs["unit_limit"],
            required_courses=base_inputs["required_courses"],
            completed_courses=base_inputs["completed_courses"],
            current_courses=base_inputs["current_courses"],
        )
        final_validation = validation

        schedule_result = check_schedule_conflicts(
            [course.code for course in plan.courses]
        )

        print("\n--- Synthetic schedule check (mock data) ---")
        print(schedule_result)

        print("\n--- Proposed plan ---")
        print(plan.model_dump_json(indent=2))

        print("\n--- Catalog and unit-range validation ---")
        print(validation)

        if validation["passed"]:
            print("\nPlan passed catalog and unit-range checks.")
            break

        issues = validation["issues"]
        if not schedule_result["passed"]:
            issues.extend(
                f"Mock schedule check: {issue}"
                for issue in schedule_result["issues"]
            )

    revision_feedback = (
            "Revise the plan to address these validation issues. "
            "Keep valid courses and use only verified catalog information.\n"
            + "\n".join(f"- {issue}" for issue in issues)
    )
else:
    print(
        f"\nPlanning stopped after {MAX_ATTEMPTS} attempt(s). "
        "The plan may need review."
    )

if final_plan is not None:
    print("\n--- Final plan ---")
    print(final_plan.model_dump_json(indent=2))

if final_validation is not None:
    print("\n--- Final validation status ---")
    print(final_validation)
