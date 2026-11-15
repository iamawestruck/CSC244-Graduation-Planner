import re

from models import GraduationPlan, PlannedCourse
from validation import (
    normalize_course_code,
    parse_course_set,
    validate_plan,
)


def prerequisite_status(text, completed, planned):
    """Check supported prerequisite expressions conservatively."""
    text = " ".join(str(text or "").upper().split())
    completed = {
        normalize_course_code(code) for code in completed
    }
    planned = {
        normalize_course_code(code) for code in planned
    }

    if text in {
        "NONE LISTED IN CATALOG.",
        "NONE LISTED IN CATALOG",
    }:
        return True, "No prerequisite listed in the supplied catalog."

    if not text:
        return False, "Prerequisite information is missing."

    code_pattern = r"[A-Z]{2,5}\s+\d+[A-Z]*"
    concurrent = set()

    # Example: "CSC 20 AND CSC 28; CSC 28 may be concurrent."
    suffix = re.fullmatch(
        rf"(.+);\s*((?:{code_pattern})"
        rf"(?:\s+AND\s+(?:{code_pattern}))*)"
        r"\s+MAY BE CONCURRENT\.?",
        text,
    )

    if suffix:
        text = suffix.group(1)
        concurrent = set(
            re.findall(code_pattern, suffix.group(2))
        )
    else:
        # Example: "CSC 130; may be concurrent."
        suffix = re.fullmatch(
            r"(.+);\s*MAY BE CONCURRENT\.?",
            text,
        )
        if suffix and re.fullmatch(
                code_pattern, suffix.group(1).strip()
        ):
            text = suffix.group(1)
            concurrent = {text.strip()}

    available = completed | (planned & concurrent)

    def evaluate(expression):
        expression = re.sub(
            r",\s*(?=OR\b)",
            " ",
            expression.strip().rstrip("."),
        )
        tokens = [
            part.strip()
            for part in re.split(
                r"(\bAND\b|\bOR\b|[()])",
                expression,
            )
            if part.strip()
        ]
        position = 0

        def atom():
            nonlocal position

            if position >= len(tokens):
                raise ValueError("Missing prerequisite operand")

            token = tokens[position]
            position += 1

            if token == "(":
                value = either()
                if (
                        position >= len(tokens)
                        or tokens[position] != ")"
                ):
                    raise ValueError("Unbalanced parentheses")
                position += 1
                return value

            if token in {"AND", "OR", ")"}:
                raise ValueError("Unexpected prerequisite token")

            # Unknown permissions, grades, status, etc. are unverified.
            return bool(
                re.fullmatch(code_pattern, token)
                and token in available
            )

        def both():
            nonlocal position
            value = atom()

            while position < len(tokens) and tokens[position] == "AND":
                position += 1
                right = atom()
                value = value and right

            return value

        def either():
            nonlocal position
            value = both()

            while position < len(tokens) and tokens[position] == "OR":
                position += 1
                right = both()
                value = value or right

            return value

        value = either()
        if position != len(tokens):
            raise ValueError("Unsupported prerequisite expression")

        return value

    try:
        # Additional semicolon clauses are required conditions.
        results = [
            evaluate(clause) for clause in text.split(";")
        ]
        passed = all(results)
    except ValueError:
        passed = False

    if passed:
        return True, "Listed course prerequisites are supported."

    return False, f"Unmet or unverified prerequisite conditions: {text}"


def fixed_credits(row):
    """Read a fixed credit value; variable credits need manual selection."""
    match = re.fullmatch(
        r"(\d+)\s*(?:hours?|units?)\.?",
        str(row["Credit Hours"]).strip(),
        re.I,
    )
    return int(match.group(1)) if match else None


def eligible_catalog(catalog, completed_courses):
    completed = parse_course_set(completed_courses)
    candidates = {}

    for _, row in catalog.iterrows():
        code = normalize_course_code(
            f"{row['Subject']} {row['Number']}"
        )
        credits = fixed_credits(row)

        if (
                code not in completed
                and credits is not None
                and credits > 0
        ):
            candidates[code] = row

    # A concurrent prerequisite must also remain a possible candidate.
    while True:
        rejected = [
            code
            for code, row in candidates.items()
            if not prerequisite_status(
                row["Prerequisites"],
                completed,
                set(candidates),
            )[0]
        ]

        if not rejected:
            return candidates

        for code in rejected:
            del candidates[code]


def build_checked_plan(
        draft,
        candidates,
        completed_courses,
        min_units,
        max_units,
):
    courses = []
    errors = []

    for selection in draft.courses:
        code = normalize_course_code(selection.code)
        row = candidates.get(code)

        if row is None:
            errors.append(
                f"{code} is not in the eligible candidate list."
            )
            continue

        # Names and credits come from the CSV, not the AI.
        courses.append(
            PlannedCourse(
                code=code,
                name=str(row["Name"]).strip(),
                credit_hours=fixed_credits(row),
                reason=selection.reason,
            )
        )

    plan = GraduationPlan(
        courses=courses,
        assumptions=draft.assumptions,
        unresolved_questions=draft.unresolved_questions,
    )

    report = validate_plan(
        plan,
        min_units,
        max_units,
        completed_courses,
    )

    completed = parse_course_set(completed_courses)
    selected_codes = {course.code for course in courses}

    # Recheck concurrency against the actual selected courses.
    for course in courses:
        ok, reason = prerequisite_status(
            candidates[course.code]["Prerequisites"],
            completed,
            selected_codes,
        )
        if not ok:
            errors.append(f"{course.code}: {reason}")

    report["issues"].extend(errors)
    report["passed"] = not report["issues"]

    report["limitations"] = [
        "Prerequisite checks support course-code AND/OR expressions "
        "and explicit concurrent enrollment. Unsupported conditions "
        "are excluded for review.",
        "Variable-credit courses require manual selection "
        "and are excluded here.",
        "Completion grades, degree fulfillment, AI explanations, "
        "actual section availability, and timetable conflicts "
        "are not verified.",
    ]

    return plan, report

def select_valid_subset(
      draft,
      candidates,
      completed_courses,
      min_units,
      max_units,
      required_courses="",
    ):
    from itertools import combinations

    original_plan, original_report = build_checked_plan(
        draft,
        candidates,
        completed_courses,
        min_units,
        max_units,
    )

    # Keep an already valid plan.
    if original_report["passed"]:
        return original_plan, original_report

    # Keep the first eligible occurrence of each proposed course.
    proposed = {}

    for selection in draft.courses:
        code = normalize_course_code(selection.code)

        if code in candidates and code not in proposed:
            proposed[code] = selection.model_copy(
                update={"code": code}
            )

    codes = list(proposed)

    # Bound the search to avoid expensive combinations.
    if len(codes) > 18:
        original_report["issues"].append(
            "Automatic subset search supports at most "
            "18 unique proposals."
        )
        return original_plan, original_report

    completed = parse_course_set(completed_courses)
    required = parse_course_set(required_courses) - completed

    credits = {
        code: fixed_credits(candidates[code])
        for code in codes
    }

    best_codes = None
    best_score = None

    for size in range(1, len(codes) + 1):
        for subset in combinations(codes, size):
            total = sum(credits[code] for code in subset)

            if not min_units <= total <= max_units:
                continue

            selected = set(subset)

            # Check prerequisites against this exact combination.
            if not all(
                    prerequisite_status(
                        candidates[code]["Prerequisites"],
                        completed,
                        selected,
                    )[0]
                    for code in subset
            ):
                continue

            # Prefer more unfinished required courses.
            # Use the AI's list order to break ties.
            score = (
                len(selected & required),
                tuple(code in selected for code in codes),
            )

            if best_score is None or score > best_score:
                best_score = score
                best_codes = subset

    if best_codes is None:
        original_report["issues"].append(
            "No supported subset of the AI proposals "
            "meets the unit range."
        )
        return original_plan, original_report

    fitted_draft = draft.model_copy(
        update={
            "courses": [
                proposed[code] for code in best_codes
            ]
        }
    )

    plan, report = build_checked_plan(
        fitted_draft,
        candidates,
        completed_courses,
        min_units,
        max_units,
    )

    original_codes = {
        normalize_course_code(selection.code)
        for selection in draft.courses
    }
    omitted = sorted(original_codes - set(best_codes))

    report["selection_notes"] = [
        f"Python selected {len(plan.courses)} courses "
        f"from {len(draft.courses)} AI proposals."
    ]

    if len(original_codes) < len(draft.courses):
        report["selection_notes"].append(
            "Duplicate proposals were removed."
        )

    if omitted:
        report["selection_notes"].append(
            "Omitted: " + ", ".join(omitted)
        )

    return plan, report