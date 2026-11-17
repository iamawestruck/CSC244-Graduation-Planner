import argparse
import json
import sys

from models import DraftPlan
from student_inputs import load_student
from tools.course_tools import course_catalog
from course_counts import course_count_issues
from planning_check import eligible_catalog, select_valid_subset


def main(argv=None): # Entry point for our code
    parser = argparse.ArgumentParser(
        description="Create a preliminary semester plan."
    )
    parser.add_argument("--student-id") # Optional additional arguments that can be implemented
    parser.add_argument("--dept-course-count", type=int)
    args = parser.parse_args(argv)

    if (args.dept_course_count is not None
        and args.dept_course_count <= 0):
        
        parser.error("--dept-course-count must be positive")

    try:
        profile = load_student(args.student_id)
        completed = profile.get("completed_courses", "")

        min_units = int(
            profile.get("min_unit_load", "").strip() or 0 # Sets the minimum/maximum amount of units or offers a default if not given
        )
        max_units = int(
            profile.get("max_unit_load", "").strip() or 18
        )

        if not 0 <= min_units <= max_units:
            raise ValueError(
                "Unit range must satisfy 0 <= minimum <= maximum."
            )

        candidates = eligible_catalog(course_catalog, completed)

        if not candidates:
            raise ValueError(
                "No supported candidates; "
                "catalog/eligibility needs review."
            )

        from workflow import make_planning_crew

    except Exception as exc:
        print(
            f"Could not initialize planner: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    inputs = {
        "intended_semester": profile.get(
            "intended_semester", "Not supplied"
        ),
        "major": profile.get("major", "Not supplied"),
        "completed_courses": completed,
        "preferences": profile.get(
            "preferences", "None supplied"
        ),
        "required_courses": profile.get(
            "remaining_required_courses", ""
        ),
        "remaining_choice_groups": profile.get(
            "remaining_choice_groups", ""
        ),
        "min_unit_load": min_units,
        "max_unit_load": max_units,
        "course_candidates": "\n".join(
            f"{code} | {row['Name']} | {row['Credit Hours']} | "
            f"{row['Requirement Group']} | "
            f"Prerequisites: {row['Prerequisites']}"
            for code, row in candidates.items()
        ),
        "revision_feedback": (
            "First attempt; no previous selection."
        ),
    }

    plan, report = None
    # Initial attempt plus at most one correction attempt.
    for attempt in range(1, 3):
        print(
            f"\nPlanning attempt {attempt}/2...",
            flush=True, # flush clears budder and pushes message to the screen when the line runs
        )

        try:
            result = make_planning_crew().kickoff(inputs=inputs)

            if result.pydantic is None:
                raise ValueError(
                    "No structured DraftPlan returned."
                )

            draft = DraftPlan.model_validate( # Verifies the data fits our model
                result.pydantic.model_dump()
            )

            plan, report = select_valid_subset(
                draft,
                candidates,
                completed,
                min_units,
                max_units,
                required_courses=inputs["required_courses"],
            )

        except Exception as exc:
            print(
                f"Attempt failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

            if attempt == 2:
                break # Was return 1, however this wouldn't show attempt 1's plan if attempt 2 crashed

            inputs["revision_feedback"] = (
                "Previous attempt failed. Return the requested "
                "DraftPlan JSON with courses containing only code "
                "and reason, plus assumptions and "
                "unresolved_questions."
            )
            continue

        if report["passed"]:
            break # If current plan meets preliminary goals, stop future attempts

        for issue in report["issues"]:
            print(f"- {issue}")

        inputs["revision_feedback"] = json.dumps({
            "previous_codes": [
                course.code for course in draft.courses
            ],
            "issues_to_fix": report["issues"],
        })

    if plan is None: # This prevents the loss of attempt 1's plan even if it didn't pass validation
        print("No plan oculd be produced.", file=sys.stderr)
        return 1
    
    # Department comparison happens after planning.
    # It does not instruct the AI to select a particular count.
    if args.dept_course_count is not None:
        report["issues"].extend(
            course_count_issues(
                planned_count=len(plan.courses),
                min_units=min_units,
                max_units=max_units,
                dept_target=args.dept_course_count,
            )
        )
        report["passed"] = not report["issues"]

    print("\n===== PRELIMINARY GRADUATION PLAN =====\n")
    print(
        json.dumps(
            plan.model_dump(exclude={"unresolved_questions"}),
            indent=2,
            ensure_ascii=False,
        )
    )

    for note in report.get("selection_notes", []):
        print(f"Selection: {note}")

    status = "PASS" if report["passed"] else "REVIEW NEEDED" # Shows up at the end of the program, checks if preliminary program passes our manual checks
    print(f"\n===== PYTHON VALIDATION: {status} =====")
    print(f"Planned credits: {report['planned_credit_hours']}")

    for issue in report["issues"]:
        print(f"- {issue}")

    for limitation in report["limitations"]:
        print(f"Note: {limitation}")

    return 0 if report["passed"] else 1


if __name__ == "__main__": # Every Python file has the __name__ variable
    sys.exit(main())