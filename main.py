import re
from datetime import datetime
import pandas as pd
from pydantic import BaseModel, Field
from crewai import Agent, Crew, Process, Task, LLM
from tools.course_tools import search_courses, get_course, check_user_requirements, retrieve_courses, course_catalog, courses as raw_courses
from dotenv import load_dotenv

load_dotenv()

local_llm = LLM(
    model="llama3.2",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    custom_openai=True,
)


class PlannedCourse(BaseModel):
    code: str = Field(
        description="Course code, such as CS 201"
    )
    name: str = Field(
        description="Course name verified in the catalog"
    )
    credit_hours: int = Field(
        description="The number of credit hours selected for this plan"
    )
    reason: str = Field(
        description="Why this course is included in the plan"
    )


class GraduationPlan(BaseModel):
    courses: list[PlannedCourse] = Field(
        description="Courses recommended for the plan"
    )
    assumptions: list[str] = Field(
        description="Assumptions made when building the plan"
    )
    unresolved_questions: list[str] = Field(
        description="Information that still needs confirmation"
    )


def parse_course_list(value: str) -> set[str]:
    """Convert 'CS 101, MATH 221' to normalized course codes."""
    return {
        " ".join(course.strip().upper().split())
        for course in value.split(",")
        if course.strip()
    }


def find_catalog_course(code: str):
    """Find a course by its normalized subject and number."""
    match = re.fullmatch(r"([A-Z]+)\s+([A-Z0-9]+)", code)

    if not match:
        return None

    subject, number = match.groups()

    matches = course_catalog[
        course_catalog["Subject"].str.upper().eq(subject)
        & course_catalog["Number"].str.strip().str.upper().eq(number)
    ]

    if matches.empty:
        return None

    return matches.iloc[0]


def credit_hours_allowed(catalog_value: str, selected: int) -> bool:
    """
    Check an integer credit selection against entries such as:
    '3 hours.', '3 OR 4 hours.', or '2 TO 4 hours.'
    """
    text = str(catalog_value).upper()
    numbers = [int(n) for n in re.findall(r"\d+", text)]

    if not numbers:
        return False

    if "OR" in text:
        return selected in numbers

    if "TO" in text and len(numbers) >= 2:
        return numbers[0] <= selected <= numbers[1]

    return selected == numbers[0]


def normalize_days(value):
    """Convert a meeting pattern such as MWF or TR into a set."""
    valid_days = set("MTWRFSU")
    return {
        char for char in str(value).strip().upper()
        if char in valid_days
    }


def parse_meeting_time(value):
    """Parse times such as '09:00 AM'. Return None if unavailable."""
    value = str(value).strip().upper()

    if not value or value == "ARRANGED":
        return None

    try:
        return datetime.strptime(value, "%I:%M %p").time()
    except ValueError:
        return None


def check_schedule_conflicts(course_codes):
    """
    Find a combination of course sections that does not overlap.
    Uses the original, non-deduplicated course CSV data.
    """
    schedule_data = raw_courses.copy()

    # Normalize course identifiers.
    schedule_data["Subject"] = (
        schedule_data["Subject"].fillna("").astype(str).str.upper().str.strip()
    )
    schedule_data["Number"] = (
        schedule_data["Number"].fillna("").astype(str).str.strip()
    )

    # Find every term in which all proposed courses appear.
    course_rows = {}

    for code in course_codes:
        match = re.fullmatch(
            r"([A-Z]+)\s+([A-Z0-9]+)",
            code.strip().upper()
        )

        if not match:
            return {
                "passed": False,
                "issues": [f"Invalid course code: {code}"],
                "selected_sections": []
            }

        subject, number = match.groups()

        rows = schedule_data[
            schedule_data["Subject"].eq(subject)
            & schedule_data["Number"].str.upper().eq(number)
        ]

        if rows.empty:
            return {
                "passed": False,
                "issues": [f"{code} was not found in the catalog."],
                "selected_sections": []
            }

        course_rows[code] = rows

    common_terms = None

    for rows in course_rows.values():
        terms = set(rows["YearTerm"].dropna().astype(str))
        common_terms = (
            terms if common_terms is None
            else common_terms & terms
        )

    if not common_terms:
        return {
            "passed": False,
            "issues": [
                "The proposed courses do not all appear in a common "
                "catalog term."
            ],
            "selected_sections": []
        }

    def get_options(rows, term):
        """Keep sections with usable days and start/end times."""
        options = []

        for _, row in rows[rows["YearTerm"].astype(str).eq(term)].iterrows():
            days = normalize_days(row["Days of Week"])
            start = parse_meeting_time(row["Start Time"])
            end = parse_meeting_time(row["End Time"])

            # Don't treat unknown meeting times as verified schedules.
            if not days or start is None or end is None or start >= end:
                continue

            options.append({
                "section": str(row.get("Section", "")),
                "crn": str(row.get("CRN", "")),
                "days": days,
                "start": start,
                "end": end,
                "display": (
                    f"{row['Subject']} {row['Number']} "
                    f"Section {row.get('Section', '')}: "
                    f"{row['Days of Week']} "
                    f"{row['Start Time']}-{row['End Time']}"
                )
            })

        return options

    def overlaps(a, b):
        """True when two sections meet on the same day and overlap."""
        shared_days = a["days"] & b["days"]

        return bool(shared_days) and (
            a["start"] < b["end"]
            and b["start"] < a["end"]
        )

    # Try each common term until a conflict-free combination is found.
    for term in sorted(common_terms):
        options_by_course = {
            code: get_options(rows, term)
            for code, rows in course_rows.items()
        }

        unavailable = [
            code for code, options in options_by_course.items()
            if not options
        ]

        if unavailable:
            continue

        # Try courses with fewer sections first to reduce search work.
        ordered_courses = sorted(
            options_by_course,
            key=lambda code: len(options_by_course[code])
        )

        selected = []

        def find_combination(index):
            if index == len(ordered_courses):
                return True

            code = ordered_courses[index]

            for option in options_by_course[code]:
                if any(overlaps(option, chosen) for chosen in selected):
                    continue

                selected.append(option)

                if find_combination(index + 1):
                    return True

                selected.pop()

            return False

        if find_combination(0):
            return {
                "passed": True,
                "term": term,
                "issues": [],
                "selected_sections": [
                    option["display"] for option in selected
                ]
            }

    return {
        "passed": False,
        "issues": [
            "No conflict-free combination of sections with known "
            "meeting days and times was found. Some courses may have "
            "only arranged or missing schedules."
        ],
        "selected_sections": []
    }




def validate_plan(
    plan: GraduationPlan,
    required_courses: str,
    completed_courses: str,
    minimum_credits: int,
) -> dict:
    required = parse_course_list(required_courses)
    completed = parse_course_list(completed_courses)

    planned_codes = [
        " ".join(course.code.strip().upper().split())
        for course in plan.courses
    ]
    planned = set(planned_codes)

    issues = []
    catalog_verified = []

    # Check for duplicate course entries.
    duplicates = sorted({
        code for code in planned_codes
        if planned_codes.count(code) > 1
    })
    if duplicates:
        issues.append(
            f"Duplicate courses in plan: {', '.join(duplicates)}"
        )

    # Verify every proposed course against the CSV.
    total_planned_credits = 0

    for course in plan.courses:
        code = " ".join(course.code.strip().upper().split())
        catalog_row = find_catalog_course(code)

        if catalog_row is None:
            issues.append(
                f"{code} was not found in the Fall 2019 catalog."
            )
            continue

        catalog_name = str(catalog_row["Name"]).strip()
        catalog_credits = str(catalog_row["Credit Hours"])

        if course.name.strip().casefold() != catalog_name.casefold():
            issues.append(
                f"{code} has a course-name mismatch. "
                f"Catalog name: '{catalog_name}'; "
                f"proposed name: '{course.name}'."
            )

        if not credit_hours_allowed(
            catalog_credits, course.credit_hours
        ):
            issues.append(
                f"{code} has an invalid credit selection of "
                f"{course.credit_hours}. Catalog entry: "
                f"'{catalog_credits}'."
            )
        else:
            total_planned_credits += course.credit_hours

        catalog_verified.append(code)

    # Check supplied requirements against completed and planned courses.
    missing = sorted(required - completed - planned)
    if missing:
        issues.append(
            f"Missing required courses: {', '.join(missing)}"
        )

    # Match the behavior of your existing checker:
    # compare planned-course credits with the supplied minimum.
    shortfall = max(0, minimum_credits - total_planned_credits)

    if shortfall:
        issues.append(
            f"Planned credits are short by {shortfall} hours. "
            f"Target: {minimum_credits}; "
            f"planned: {total_planned_credits}."
        )

    return {
        "passed": not issues,
        "issues": issues,
        "missing_courses": missing,
        "planned_credit_hours": total_planned_credits,
        "minimum_credits": minimum_credits,
        "credit_shortfall": shortfall,
        "catalog_verified_courses": sorted(set(catalog_verified)),
    }

#  course agent


course_agent = Agent(
    role="University Course Catalog Researcher",
    goal=(
        "Find relevant courses and verify their details "
        "using the provided course catalog tools."
    ),
    backstory=(
        "You specialize in university course catalogs. "
        "You use search_courses and get_course to verify "
        "course information. The available dataset is "
        "from Fall 2019, not the current catalog."
    ),
    tools=[search_courses, get_course],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)

#  planning agent

planning_agent = Agent(
    role="Graduation Planning Specialist",
    goal=(
        "Turn verified course information and student priorities "
        "into a useful preliminary graduation plan."
    ),
    backstory=(
        "You help students organize courses into a potential "
        "academic plan. You distinguish required courses from "
        "recommended courses, respect prerequisites when verified, "
        "and clearly identify missing degree information. "
        "You never invent degree requirements or course availability."
    ),
    tools=[retrieve_courses],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)

#  requirement agent


requirement_agent = Agent(
    role="Graduation Requirement Auditor",
    goal=(
        "Audit a preliminary graduation plan against "
        "the student's supplied degree requirements "
        "and identify missing courses or credit shortfalls."
    ),
    backstory=(
        "You independently review proposed graduation plans. "
        "You use the check_user_requirements tool for "
        "course-code and credit-hour comparisons. You report "
        "missing information, distinguish verified issues "
        "from unresolved questions, and never invent degree "
        "requirements or claim official graduation eligibility."
    ),
    tools=[check_user_requirements],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)


#  Coordination agent


coordinator = Agent(
    role="Graduation Planner Coordinator",
    goal=(
        "Coordinate the specialist agents to answer the student's request with an accurate, organized graduation plan that lists the classes."
    ),
    backstory=(
        "You are responsible for coordinating a graduation-planning team. First determine what information the student needs. "
        "Delegate catalog research to the Course Catalog Researcher and planning analysis to the Graduation Planning Specialist. "
        "Check that the final answer distinguishes verified facts from assumptions and identifies missing information. "
        "Do not claim that courses are currently offered or that degree requirements are satisfied without supporting data."
        "Ensure the requirement-checking task reviews the preliminary plan before presenting the final report. "
        "Clearly communicate any failures and unresolved checks."
    ),
    llm=local_llm,
    allow_delegation=True,
    verbose=True,
)


# 4. Main planning task


graduation_task = Task(
    description=(
        "Create a preliminary course plan for: {topic}.\n"
        "Student priorities: {priorities}\n"
        "Completed courses: {completed_courses}\n"
        "Required courses supplied by the student: {required_courses}\n"
        "Minimum planned credit hours: {minimum_credits}\n"
        "Planning constraints: {constraints}\n\n"
        "Previous Python validation feedback:\n"
        "{revision_feedback}\n\n"
        "Do not invent requirements or prerequisites. If the "
        "available information is insufficient, explain this in "
        "unresolved_questions.\n\n"
        "Return the result in the GraduationPlan schema. "
        "Do not add Markdown or commentary outside the structured output."
        "Create a graduation course plan based on the student's inputs.\n\n"
        "Before recommending courses, use the Retrieve courses from "
        "vector database tool to search for courses relevant to the "
        "student's interests and requirements.\n\n"
        "Only recommend courses supported by the retrieved catalog "
        "records. Use the exact course codes, names, and credit hours "
        "from the catalog. Do not invent course information.\n\n"
        "If the retrieved records do not provide enough information, "
        "state what is missing rather than guessing. Include any "
        "assumptions and unresolved questions."
    ),
    expected_output=(
        "A GraduationPlan containing verified proposed courses, "
        "selected credit hours, reasons, assumptions, and unresolved questions."
    ),
    output_pydantic=GraduationPlan,
    agent=planning_agent,
)


requirement_check_task = Task(
    description=(
        "Audit the preliminary graduation plan produced "
        "by the planning workflow.\n\n"

        "Student-provided degree requirements: "
        "{required_courses}\n"
        "Student's completed courses: {completed_courses}\n"
        "Proposed courses: {planned_courses}\n"
        "Minimum required credit hours: {minimum_credits}\n"
        "Planned credit hours: {planned_credit_hours}\n\n"

        "Use the check_degree_requirements tool to compare "
        "the supplied course codes and credit hours.\n"
        "Do not assume that a course satisfies a degree "
        "requirement merely because its name sounds relevant.\n\n"

        "Also review the preliminary plan for prerequisite "
        "concerns, unsupported assumptions, and missing "
        "information. Flag these for verification rather "
        "than claiming that the tool checked them.\n\n"

        "Return a validation report containing passed checks, "
        "identified issues, unresolved questions, and "
        "recommended corrections. State clearly that this "
        "is not an official degree audit."
    ),
    expected_output=(
        "A requirement validation report with the results "
        "of the Python checks, identified issues, unresolved "
        "requirements, and recommended corrections."
    ),
    agent=requirement_agent,
    context=[graduation_task],
)


#Crew + Running

planning_crew = Crew(
    agents=[planning_agent],
    tasks=[graduation_task],
    process=Process.sequential,
    verbose=True,
)

MAX_ATTEMPTS = 3

base_inputs = {
    "topic": "machine learning",
    "priorities": "Required courses first, then prerequisites.",
    "constraints": "No confirmed current course schedule.",
    "completed_courses": "CS 101",
    "required_courses": "CS 101, CS 201, MATH 221",
    "minimum_credits": 30,
}

revision_feedback = "Create the initial plan."
final_plan = None
final_validation = None

for attempt in range(1, MAX_ATTEMPTS + 1):
    print(f"\n--- Planning attempt {attempt} ---")

    result = planning_crew.kickoff(
        inputs={
            **base_inputs,
            "revision_feedback": revision_feedback,
        }
    )

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

test_plan = GraduationPlan(
    courses=[
        PlannedCourse(
            code="CS 201",
            name="Intentionally incorrect name",
            credit_hours=4,
            reason="Testing catalog validation.",
        )
    ],
    assumptions=[],
    unresolved_questions=[],
)

test_result = validate_plan(
    plan=test_plan,
    required_courses="CS 101, CS 201, MATH 221",
    completed_courses="CS 101",
    minimum_credits=30,
)

print(test_result)