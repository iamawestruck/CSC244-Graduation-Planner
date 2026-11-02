import re

from models import GraduationPlan
from tools.course_tools import course_catalog


def parse_course_list(value: str) -> set[str]:
    """Convert 'CS 101, MATH 221' into normalized course codes."""
    return {
        " ".join(course.strip().upper().split())
        for course in value.split(",")
        if course.strip()
    }


def find_catalog_course(code: str):
    """Find a course in the CSV using its subject and number."""
    match = re.fullmatch(r"([A-Z]+)\s+([A-Z0-9]+)", code.strip().upper())

    if not match:
        return None

    subject, number = match.groups()

    subjects = (
        course_catalog["Subject"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )
    numbers = (
        course_catalog["Number"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    matches = course_catalog[subjects.eq(subject) & numbers.eq(number)]

    if matches.empty:
        return None

    return matches.iloc[0]


def credit_hours_allowed(catalog_value: str, selected: int) -> bool:
    """Check a credit selection against entries such as '3 OR 4 hours.'."""
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

    issues = []
    catalog_verified = set()
    credited_codes = set()
    total_planned_credits = 0

    duplicates = sorted({
        code for code in planned_codes
        if planned_codes.count(code) > 1
    })
    if duplicates:
        issues.append(f"Duplicate courses in plan: {', '.join(duplicates)}")

    for course in plan.courses:
        code = " ".join(course.code.strip().upper().split())
        catalog_row = find_catalog_course(code)

        if catalog_row is None:
            issues.append(f"{code} was not found in the provided catalog.")
            continue

        catalog_verified.add(code)
        catalog_name = str(catalog_row["Name"]).strip()
        catalog_credits = str(catalog_row["Credit Hours"])

        if course.name.strip().casefold() != catalog_name.casefold():
            issues.append(
                f"{code} has a course-name mismatch. "
                f"Catalog name: '{catalog_name}'; "
                f"proposed name: '{course.name}'."
            )

        credits_valid = credit_hours_allowed(
            catalog_credits,
            course.credit_hours,
        )
        if not credits_valid:
            issues.append(
                f"{code} has an invalid credit selection of "
                f"{course.credit_hours}. Catalog entry: "
                f"'{catalog_credits}'."
            )
        elif code not in credited_codes:
            total_planned_credits += course.credit_hours
            credited_codes.add(code)

    missing = sorted(required - completed - catalog_verified)
    if missing:
        issues.append(f"Missing required courses: {', '.join(missing)}")

    shortfall = max(0, minimum_credits - total_planned_credits)
    if shortfall:
        issues.append(
            f"Planned credits are short by {shortfall} hours. "
            f"Target: {minimum_credits}; planned: {total_planned_credits}."
        )

    return {
        "passed": not issues,
        "issues": issues,
        "missing_courses": missing,
        "planned_credit_hours": total_planned_credits,
        "minimum_credits": minimum_credits,
        "credit_shortfall": shortfall,
        "catalog_verified_courses": sorted(catalog_verified),
    }