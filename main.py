
from schedule import check_schedule_conflicts
from validation import (
    parse_course_list,
    find_catalog_course,
    validate_plan,
)
from workflow import planning_crew

MAX_ATTEMPTS = 1

base_inputs = {
    "topic": "machine learning",
    "priorities": "Required courses first, then prerequisites.",
    "constraints": "No confirmed current course schedule.",
    "completed_courses": "CS 101",
    "required_courses": "CS 101, CS 201, MATH 221",
    "minimum_credits": 30,
}
required_codes = parse_course_list(base_inputs["required_courses"])
completed_codes = parse_course_list(base_inputs["completed_courses"])

missing_required_codes = sorted(
    code
    for code in required_codes - completed_codes
    if find_catalog_course(code) is None
)

print("\n--- Required course catalog check ---")
if missing_required_codes:
    print(
        "These required course codes aren't in the CSV:",
        ", ".join(missing_required_codes),
    )
else:
    print("All uncompleted required courses are in the CSV.")

revision_feedback = "Create the initial plan."
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
        print("\n--- Planner output error ---")
        print(exc)
        final_plan = None
        final_validation = {
            "passed": False,
            "issues": [
                f"Planner returned invalid structured output: {exc}"
            ],
        }
        break

    # Get the structured result from the planning task.
    task_output = result.tasks_output[0]
    plan = task_output.pydantic

    if plan is None:
        issues = [
            "The model did not return a valid GraduationPlan "
            "structured output. Retry using the required schema."
        ]

        final_plan = None
        final_validation = {
            "passed": False,
            "issues": issues,
        }

    else:
        # Validate actual generated courses, not hardcoded course lists.
        validation = validate_plan(
            plan=plan,
            required_courses=base_inputs["required_courses"],
            completed_courses=base_inputs["completed_courses"],
            minimum_credits=base_inputs["minimum_credits"],
        )


        schedule_result = check_schedule_conflicts(
            [course.code for course in plan.courses]
        )

        print("\n--- Schedule validation ---")
        print(schedule_result)

        if not schedule_result["passed"]:
            print("Schedule requires further review.")
        else:
            print("Conflict-free section combination found.")
            for section in schedule_result["selected_sections"]:
                print(section)

        final_plan = plan
        final_validation = validation

        print("\n--- Proposed plan ---")
        print(plan.model_dump_json(indent=2))

        print("\n--- Python validation ---")
        print(validation)

        if validation["passed"]:
            print("\nPlan passed the implemented Python checks.")
            break

        issues = validation["issues"]

    # Feed only the actual errors back to the next planning attempt.
    revision_feedback = (
        "Revise your previous plan to address these Python validation "
        "issues. Keep valid courses, correct invalid details, and add "
        "verified courses as needed. Do not invent catalog information.\n"
        + "\n".join(f"- {issue}" for issue in issues)
    )

else:
    print("\nRetry limit reached. Plan still needs review.")

if final_plan is not None:
    print("\n--- Final plan ---")
    print(final_plan.model_dump_json(indent=2))

if final_validation is not None:
    print("\n--- Final validation status ---")
    print(final_validation)

#
# test_plan = GraduationPlan(
#     courses=[
#         PlannedCourse(
#             code="CS 201",
#             name="Intentionally incorrect name",
#             credit_hours=4,
#             reason="Testing catalog validation.",
#         )
#     ],
#     assumptions=[],
#     unresolved_questions=[],
# )
#
# test_result = validate_plan(
#     plan=test_plan,
#     required_courses="CS 101, CS 201, MATH 221",
#     completed_courses="CS 101",
#     minimum_credits=30,
# )
#
# print(test_result)