import re #regex

from models import GraduationPlan
from tools.course_tools import course_catalog


# Standardizes different formats of codes for further use
def normalize_course_code(code: str) -> str:
    
    return " ".join(str(code).strip().upper().split())


# Converts individual courses into a normalized course set, set prevents duplicates
def parse_course_set(value: str) -> set[str]:
    
    return {
        normalize_course_code(course)
        for course in str(value or "").split(",")
        if course.strip()
    }


# Looks up a single course in the catalog DataFrame by its code, returns its row or None
def find_catalog_course(code: str):
    match = re.fullmatch(
        r"([A-Z]+)\s+([A-Z0-9]+)", # This requires string to be letters, whitespace, then letters/digits
        normalize_course_code(code), 
    ) 

    if not match:
        return None

    subject, number = match.groups() # Used for readability

    matches = course_catalog[
        course_catalog["Subject"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq(subject) # could be .eq(match[1])
        & course_catalog["Number"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq(number) # could be .eq(match[2])
        ]

    if matches.empty:
        return None

    return matches.iloc[0] # Returns first matching code


#Returns True or False based on if the credit amount is valid
def credit_hours_allowed(catalog_value: str, selected: int) -> bool:
    """Check fixed credits, ranges, or two explicit alternatives."""
    text = str(catalog_value).upper().strip()

    # Examples: "3 hours.", "1 TO 12 hours.", "1 OR 3 hours."
    match = re.fullmatch( # Requires a strict match
        r"(\d+)(?:\s*(TO|OR|-)\s*(\d+))?" #(?......?) makes chunk optional
        r"\s*(?:HOURS?|UNITS?)\.?",
        text,
    )

    if not match:
        return False

    first = int(match.group(1))
    operator = match.group(2) # No if match.group(2) else None needed because of initial match creation
    second = int(match.group(3)) if match.group(3) else None

    if operator in {"TO", "-"}:
        return first <= selected <= second # Will return true if equation is valid
    elif operator == "OR":
        return selected in {first, second}
    else:
        return selected == first


# Collects a list of issues and returns them at the end of the terminal after running the code alongside the preliminary plan
def validate_plan(
        plan: GraduationPlan, # Allows for quick changing of model
        min_unit_load: int,
        max_unit_load: int,
        completed_courses: str = "",
) -> dict:

    if min_unit_load < 0 or max_unit_load < min_unit_load:
        issues.append(
            "Invalid unit range: minimum must be nonnegative "
            "and maximum must be at least the minimum."
        )

    issues = []

    planned_codes = [
        normalize_course_code(course.code)
        for course in plan.courses
    ]

    duplicates = sorted({ # This is a sorted set, shows each entry once and in alphabetical order
        code for code in planned_codes # both 'code' play different rolls
        if planned_codes.count(code) > 1
    })

    if duplicates:
        issues.append(
            f"Duplicate courses in plan: {', '.join(duplicates)}"
        )

    if not plan.courses:
        issues.append("The plan contains no courses.")    

    completed = parse_course_set(completed_courses)
    total_planned_credits = 0

    for course, code in zip(plan.courses, planned_codes): # Pairs plan.courses and planned_codes into a tuple
        if code in completed:
            issues.append(f"{code} is already completed.")

        selected_credits = course.credit_hours # Checks credits of current course in loop

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

        if selected_name.casefold() != normalized_catalog_name.casefold(): # Checks for discrepancies 
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

    return { # Returns a dictionary
        "passed": not issues, # Returns a Boolean, used to define if preliminary plan PASS or REVIEW NEEDED. Reports True if no issues 
        "planned_credit_hours": total_planned_credits, # int
        "issues": issues, # list[str]
        "limitations": [ # list[str]
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