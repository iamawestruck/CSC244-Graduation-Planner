import re

from models import GraduationPlan
from tools.course_tools import course_catalog


def normalize_course_code(code: str) -> str:
    return " ".join(str(code).strip().upper().split())


def parse_course_list(value: str) -> set[str]:
    """Convert a comma-separated course list to normalized codes."""
    return {
        normalize_course_code(course)
        for course in str(value or "").split(",")
        if course.strip()
    }


def find_catalog_course(code: str):
    """Find a course by its subject and number."""
    match = re.fullmatch(r"([A-Z]+)\s+([A-Z0-9]+)", normalize_course_code(code))

    if not match:
        return None

    subject, number = match.groups()

    matches = course_catalog[
        course_catalog["Subject"].str.strip().str.upper().eq(subject)
        & course_catalog["Number"].str.strip().str.upper().eq(number)
        ]

    if matches.empty:
        return None

    return matches.iloc[0]


def credit_hours_allowed(catalog_value: str, selected: int) -> bool:
    """Check a selected credit amount against catalog values like '3 hours.' or '1 TO 12 hours.'."""
    text = str(catalog_value).upper()
    numbers = [int(number) for number in re.findall(r"\d+", text)]

    if not numbers:
        return False

    if "OR" in text:
        return selected in numbers

    if "TO" in text and len(numbers) >= 2:
        return numbers[0] <= selected <= numbers[1]

    return selected == numbers[0]
def validate_plan(

        plan: GraduationPlan,
        min_unit_load: int,
        unit_limit: int,
        required_courses: str = "",
        completed_courses: str = "",
        current_courses: str = "",
) -> dict:
    """Check catalog details, course repeats, required-course priority, and unit range."""
    issues = []
    planned_codes = [
        normalize_course_code(course.code)
        for course in plan.courses
    ]

    duplicates = sorted({
        code for code in planned_codes
        if planned_codes.count(code) > 1
    })
    if duplicates:
        issues.append(f"Duplicate courses in plan: {', '.join(duplicates)}")

    completed = parse_course_list(completed_courses)
    current = parse_course_list(current_courses)
    already_taken = completed | current

    total_planned_credits = 0
    catalog_verified = []

    for course, code in zip(plan.courses, planned_codes):
        if code in already_taken:
            issues.append(f"{code} is already completed or in progress.")

        selected_credits = course.credit_hours
        if selected_credits <= 0:
            issues.append(
                f"{code} has an invalid credit amount: {selected_credits}."
            )
        else:
            total_planned_credits += selected_credits

        catalog_row = find_catalog_course(code)
        if catalog_row is None:
            issues.append(f"{code} was not found in the provided catalog.")
            continue

        catalog_verified.append(code)
        catalog_name = str(catalog_row["Name"]).strip()
        catalog_credits = str(catalog_row["Credit Hours"])

        if course.name.strip().casefold() != catalog_name.casefold():
            issues.append(
                f"{code} has a course-name mismatch. "
                f"Catalog name: '{catalog_name}'; proposed name: '{course.name}'."
            )

        if not credit_hours_allowed(catalog_credits, selected_credits):
            issues.append(
                f"{code} has an invalid credit selection of {selected_credits}. "
                f"Catalog entry: '{catalog_credits}'."
            )

    required = parse_course_list(required_courses)
    required_to_schedule = required - completed - current
    cataloged_required = {
        code for code in required_to_schedule
        if find_catalog_course(code) is not None
    }

    if cataloged_required and not (cataloged_required & set(planned_codes)):
        issues.append(
            "Plan does not include an unfinished required course found in the catalog."
        )

    if min_unit_load > unit_limit:
        issues.append(
            f"Invalid unit range: minimum is {min_unit_load}, "
            f"but maximum is {unit_limit}."
        )
    elif total_planned_credits < min_unit_load:
        issues.append(
            f"Unit load is below the minimum: plan has {total_planned_credits} "
            f"units; minimum is {min_unit_load}."
        )

    if total_planned_credits > unit_limit:
        issues.append(
            f"Unit limit exceeded: plan has {total_planned_credits} units; "
            f"the limit is {unit_limit}."
        )

    return {
        "passed": not issues,
        "issues": issues,
        "planned_credit_hours": total_planned_credits,
        "min_unit_load": min_unit_load,
        "unit_limit": unit_limit,
        "catalog_verified_courses": catalog_verified,
        "limitations": [
            "This check does not verify prerequisites or actual course availability."
        ],
    }