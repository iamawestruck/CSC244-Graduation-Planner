import re

from models import GraduationPlan
from tools.course_tools import course_catalog


def normalize_course_code(code: str) -> str:
    """Standardize a course code's capitalization and spacing."""
    return " ".join(str(code).strip().upper().split())


def parse_course_set(value: str) -> set[str]:
    """Convert comma-separated course codes into a normalized set."""
    return {
        normalize_course_code(course)
        for course in str(value or "").split(",")
        if course.strip()
    }


def find_catalog_course(code: str):
    """Return the matching catalog row, or None."""
    match = re.fullmatch(
        r"([A-Z]+)\s+([A-Z0-9]+)",
        normalize_course_code(code),
    )

    if not match:
        return None

    subject, number = match.groups()

    matches = course_catalog[
        course_catalog["Subject"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq(subject)
        & course_catalog["Number"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq(number)
        ]

    if matches.empty:
        return None

    return matches.iloc[0]


def credit_hours_allowed(catalog_value: str, selected: int) -> bool:
    """Check fixed credits, ranges, or two explicit alternatives."""
    text = str(catalog_value).upper().strip()

    # Examples: "3 hours.", "1 TO 12 hours.", "1 OR 3 hours."
    match = re.fullmatch(
        r"(\d+)(?:\s*(TO|OR|-)\s*(\d+))?"
        r"\s*(?:HOURS?|UNITS?)\.?",
        text,
    )

    if not match:
        return False

    first = int(match.group(1))
    operator = match.group(2)
    second = int(match.group(3)) if match.group(3) else None

    if operator in {"TO", "-"}:
        return first <= selected <= second

    if operator == "OR":
        return selected in {first, second}

    return selected == first


def validate_plan(
        plan: GraduationPlan,
        min_unit_load: int,
        max_unit_load: int,
        completed_courses: str = "",
) -> dict:
    """Check a preliminary plan and return issues and limitations."""
    issues = []

    if min_unit_load < 0 or max_unit_load < min_unit_load:
        issues.append(
            "Invalid unit range: minimum must be nonnegative "
            "and maximum must be at least the minimum."
        )

    planned_codes = [
        normalize_course_code(course.code)
        for course in plan.courses
    ]

    duplicates = sorted({
        code
        for code in planned_codes
        if planned_codes.count(code) > 1
    })

    if duplicates:
        issues.append(
            f"Duplicate courses in plan: {', '.join(duplicates)}"
        )

    completed = parse_course_set(completed_courses)
    total_planned_credits = 0

    if not plan.courses:
        issues.append("The plan contains no courses.")

    for course, code in zip(plan.courses, planned_codes):
        if code in completed:
            issues.append(f"{code} is already completed.")

        selected_credits = course.credit_hours

        if selected_credits <= 0:
            issues.append(
                f"{code} has an invalid credit amount: "
                f"{selected_credits}."
            )
        else:
            # Sum the model's reported credits.
            # Catalog mismatches are flagged separately below.
            total_planned_credits += selected_credits

        catalog_row = find_catalog_course(code)

        if catalog_row is None:
            issues.append(
                f"{code} was not found in the supplied catalog."
            )
            continue

        catalog_name = str(catalog_row["Name"]).strip()
        selected_name = " ".join(str(course.name).split())
        normalized_catalog_name = " ".join(catalog_name.split())

        if selected_name.casefold() != normalized_catalog_name.casefold():
            issues.append(
                f"{code} has an incorrect name: {course.name!r}. "
                f"Catalog name: {catalog_name!r}."
            )

        catalog_credits = str(catalog_row["Credit Hours"]).strip()

        if not credit_hours_allowed(catalog_credits, selected_credits):
            issues.append(
                f"{code} has unsupported or unverifiable credits: "
                f"{selected_credits}. "
                f"Catalog value: {catalog_credits!r}."
            )

    if total_planned_credits < min_unit_load:
        issues.append(
            f"Planned credits ({total_planned_credits}) are below "
            f"the required minimum of ({min_unit_load})."
        )

    if total_planned_credits > max_unit_load:
        issues.append(
            f"Planned credits ({total_planned_credits}) are above "
            f"the required maximum of ({max_unit_load})."
        )

    return {
        "passed": not issues,
        "planned_credit_hours": total_planned_credits,
        "issues": issues,
        "limitations": [
            "Credit totals sum the model-reported positive credits; "
            "catalog mismatches are reported separately.",
            "Prerequisites, concurrent enrollment, permissions, "
            "and other enrollment restrictions are not checked.",
            "Degree requirement fulfillment and course-selection "
            "reasons are not checked.",
            "Actual section availability and schedule conflicts "
            "are not checked.",
        ],
    }

# import re
# from models import GraduationPlan
# from tools.course_tools import course_catalog
#
#
# # Standardizes different formats of codes for further use, overlaps with _parse_codes
# def normalize_course_code(code: str) -> str:
#     return " ".join(str(code).strip().upper().split())
#
#
# # Converts individual courses into a normalized course set
# def parse_course_set(value: str) -> set[str]:
#     return {
#         normalize_course_code(course)
#         for course in str(value or "").split(",")
#         if course.strip()
#     }
#
#
# #Looks up a single course in the catalog DataFrame by its code, returns its row or None
# def find_catalog_course(code: str):
#     match = re.fullmatch(r"([A-Z]+)\s+([A-Z0-9]+)", normalize_course_code(code)) # This requires string to be letters, whitespace, then letters/digits
#
#     if not match:
#         return None
#
#     subject, number = match.groups() # Used for readability
#
#     matches = course_catalog[
#         course_catalog["Subject"].str.strip().str.upper().eq(subject) #could be .eq(match[1])
#         & course_catalog["Number"].str.strip().str.upper().eq(number) #could be .eq(match[2])
#     ]
#
#     if matches.empty:
#         return None
#
#     return matches.iloc[0] # Returns first matching code
#
#
# ##Returns True or False based on if the credit amount is valid
#  #def credit_hours_allowed(catalog_value: str, selected: int) -> bool: # Not in use
#   #   """Check a selected credit amount against catalog values like '3 hours.' or '1 TO 12 hours.'."""
#   #   text = str(catalog_value).upper() # Converts all text to uppercase
#   #  numbers = [int(number) for number in re.findall(r"\d+", text)] # Pulls out every number in text
#   #   if not numbers:
#   #       return False # Checks quickly if numbers exist, otherwise return False
#   #   if "OR" in text:
#   #       return selected in numbers
#
# #     if "TO" in text and len(numbers) >= 2:
# #         return numbers[0] <= selected <= numbers[1]
#
#  #    return selected == numbers[0]
#
# # Collects a list of issues and returns them at the end of the main alongside the preliminary plan
# def validate_plan(
#         plan: GraduationPlan, # Allows for quick changing of plan
#         min_unit_load: int,
#         max_unit_load: int,
#         # required_courses: str = "", # Isn't in use in current version
#         completed_courses: str = "",
# ) -> dict:
#
#     issues = []
#
#     planned_codes = []
#     for course in plan.courses:
#         planned_codes.append(normalize_course_code(course.code))
#
#     duplicates = sorted({ # Counts every course, counting duplicates
#         code for code in planned_codes
#         if planned_codes.count(code) > 1
#     })
#     if duplicates:
#         issues.append(f"Duplicate courses in plan: {', '.join(duplicates)}")
#
#     completed = parse_course_set(completed_courses)
#
#     total_planned_credits = 0
#     # catalog_verified = []
#
#     for course, code in zip(plan.courses, planned_codes): # Pairs plan.courses and planned_codes into a tuple
#         if code in completed:
#             issues.append(f"{code} is already completed.")
#
#         selected_credits = course.credit_hours
#         if selected_credits <= 0:
#             issues.append(
#                 f"{code} has an invalid credit amount: {selected_credits}."
#             )
#         else:
#             total_planned_credits += selected_credits
#
#
#     if total_planned_credits < min_unit_load: # Creates issue if planned credits are less than minimum
#         issues.append(
#             f"Planned credits ({total_planned_credits}) are below the required minimum of ({min_unit_load})."
#         )
#
#     if total_planned_credits > max_unit_load: # Creates issue if planned credits are more than maximum
#         issues.append(
#             f"Planned credits ({total_planned_credits}) are above the required maximum of ({max_unit_load})."
#         )
#
#     #limitations = []
#
#     return {
#         "passed": not issues,
#         "planned_credit_hours": total_planned_credits,
#         "issues": issues,
#         #"limitations": limitations
#     }