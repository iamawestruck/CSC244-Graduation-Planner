import re

from models import GraduationPlan
try:
    from tools.course_tools import course_catalog
except ModuleNotFoundError:
    from course_tools import course_catalog


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