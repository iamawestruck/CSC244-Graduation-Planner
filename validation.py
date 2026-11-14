import re
from models import GraduationPlan
from tools.course_tools import course_catalog


# Standardizes different formats of codes for further use, overlaps with _parse_codes 
def normalize_course_code(code: str) -> str:
    return " ".join(str(code).strip().upper().split())


# Converts individual courses into a normalized course set
def parse_course_set(value: str) -> set[str]:
    return {
        normalize_course_code(course)
        for course in str(value or "").split(",")
        if course.strip()
    }


#Looks up a single course in the catalog DataFrame by its code, returns its row or None
def find_catalog_course(code: str):
    match = re.fullmatch(r"([A-Z]+)\s+([A-Z0-9]+)", normalize_course_code(code)) # This requires string to be letters, whitespace, then letters/digits

    if not match:
        return None

    subject, number = match.groups() # Used for readability

    matches = course_catalog[
        course_catalog["Subject"].str.strip().str.upper().eq(subject) #could be .eq(match[1])
        & course_catalog["Number"].str.strip().str.upper().eq(number) #could be .eq(match[2])
    ]

    if matches.empty:
        return None

    return matches.iloc[0] # Returns first matching code


#Returns True or False based on if the credit amount is valid
# def credit_hours_allowed(catalog_value: str, selected: int) -> bool: # Not in use
#     """Check a selected credit amount against catalog values like '3 hours.' or '1 TO 12 hours.'."""
#     text = str(catalog_value).upper() # Converts all text to uppercase
#     numbers = [int(number) for number in re.findall(r"\d+", text)] # Pulls out every number in text

#     if not numbers:
#         return False # Checks quickly if numbers exist, otherwise return False

#     if "OR" in text:
#         return selected in numbers

#     if "TO" in text and len(numbers) >= 2:
#         return numbers[0] <= selected <= numbers[1]

#     return selected == numbers[0]

# Collects a list of issues and returns them at the end of the main alongside the preliminary plan
def validate_plan(
        plan: GraduationPlan, # Allows for quick changing of plan
        min_unit_load: int,
        max_unit_load: int, 
        # required_courses: str = "", # Isn't in use in current version
        completed_courses: str = "",
) -> dict:
    
    issues = []

    planned_codes = []
    for course in plan.courses: 
        normalize_course_code(course.code)

    duplicates = sorted({ # Counts every course, counting duplicates
        code for code in planned_codes 
        if planned_codes.count(code) > 1 
    })
    if duplicates:
        issues.append(f"Duplicate courses in plan: {', '.join(duplicates)}")

    completed = parse_course_set(completed_courses)

    total_planned_credits = 0
    # catalog_verified = []

    for course, code in zip(plan.courses, planned_codes): # Pairs plan.courses and planned_codes into a tuple
        if code in completed:
            issues.append(f"{code} is already completed.")

        selected_credits = course.credit_hours
        if selected_credits <= 0:
            issues.append(
                f"{code} has an invalid credit amount: {selected_credits}."
            )
        else:
            total_planned_credits += selected_credits


    if total_planned_credits < min_unit_load: # Creates issue if planned credits are less than minimum
        issues.append(
            f"Planned credits ({total_planned_credits}) are below the required minimum of ({min_unit_load})."
        )

    if total_planned_credits > max_unit_load: # Creates issue if planned credits are more than maximum
        issues.append(
            f"Planned credits ({total_planned_credits}) are above the required maximum of ({max_unit_load})."
        )

    #limitations = []

    return {
        "passed": not issues,
        "planned_credit_hours": total_planned_credits,
        "issues": issues,
        #"limitations": limitations
    }