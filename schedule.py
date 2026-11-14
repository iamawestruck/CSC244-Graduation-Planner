import re
from datetime import datetime
from tools.course_tools import courses as raw_courses



def normalize_days(value):
    """Convert a meeting pattern such as MWF or TR into a set."""
    valid_days = set("MTWRFSU")
    return {
        char for char in str(value).strip().upper()
        if char in valid_days
    }


def parse_meeting_time(value):
    """Parse times such as '09:00 AM'; return None if unavailable."""
    value = str(value).strip().upper()

    if not value:
        return None

    if value == "ARRANGED":
        return "CUSTOM"
    
    try:
        return datetime.strptime(value, "%I:%M %p").time()
    except ValueError:
        return None


def check_schedule_conflicts(course_codes):
    """Find a combination of course sections that does not overlap."""
    if not course_codes:
        return {
            "passed": False,
            "issues": ["No courses were provided for schedule checking."],
            "selected_sections": [],
        }

    schedule_data = raw_courses.copy()
    schedule_data["Subject"] = (
        schedule_data["Subject"].fillna("").astype(str).str.upper().str.strip()
    )
    schedule_data["Number"] = (
        schedule_data["Number"].fillna("").astype(str).str.strip()
    )

    course_rows = {}

    for original_code in course_codes:
        code = " ".join(str(original_code).strip().upper().split())
        match = re.fullmatch(r"([A-Z]+)\s+([A-Z0-9]+)", code)

        if not match:
            return {
                "passed": False,
                "issues": [f"Invalid course code: {original_code}"],
                "selected_sections": [],
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
                "selected_sections": [],
            }

        course_rows[code] = rows

    common_terms = None
    for rows in course_rows.values():
        terms = set(rows["YearTerm"].dropna().astype(str))
        common_terms = terms if common_terms is None else common_terms & terms

    if not common_terms:
        return {
            "passed": False,
            "issues": ["The proposed courses do not all appear in a common catalog term."],
            "selected_sections": [],
        }

    def get_options(rows, term):
        options = []

        for _, row in rows[rows["YearTerm"].astype(str).eq(term)].iterrows():
            days = normalize_days(row["Days of Week"])
            start = parse_meeting_time(row["Start Time"])
            end = parse_meeting_time(row["End Time"])

            day_text = str(row["Days of Week"]).strip().upper()
            if not re.fullmatch(r"[MTWRFSU\s,/]+", day_text):
                continue

            if not days or start in (None, "CUSTOM") or end in (None, "CUSTOM"):
                continue

            if start >= end:
                continue

            options.append({
                "term": term,
                "days": days,
                "start_time": start,
                "end_time": end,
                "section_status": str(
                    row.get("Section Status", "Not specified")
                ),
            })

        return options

    def overlaps(first, second):
        return bool(first["days"] & second["days"]) and (
                first["start_time"] < second["end_time"]
                and second["start_time"] < first["end_time"]
        )

    def select_sections(codes, options, selected, index=0):
        if index == len(codes):
            return selected.copy()

        code = codes[index]

        for option in options[code]:
            if any(overlaps(option, other) for other in selected):
                continue

            selected.append({"code": code, **option})

            result = select_sections(
                codes, options, selected, index + 1
            )

            if result is not None:
                return result

            # Try another section if this choice leads to a conflict.
            selected.pop()

        return None

    codes = list(course_rows)

    for term in sorted(common_terms):
        if not term.strip() or term.strip().lower() in {
            "nan", "none", "<na>"
        }:
            continue

        options = {
            code: get_options(rows, term)
            for code, rows in course_rows.items()
        }

        if any(not sections for sections in options.values()):
            continue

        selected = select_sections(codes, options, [])

        if selected is not None:
            for section in selected:
                section["days"] = "".join(
                    day for day in "MTWRFSU"
                    if day in section["days"]
                )
                section["start_time"] = (
                    section["start_time"].strftime("%I:%M %p")
                )
                section["end_time"] = (
                    section["end_time"].strftime("%I:%M %p")
                )

            return {
                "passed": True,
                "issues": [],
                "selected_sections": selected,
                "limitations": [
                    "Checks only the supplied CSV meeting times. "
                    "Synthetic rows are demo data.",
                    "Each row is assumed to be a complete section; "
                    "linked lectures/labs need separate handling.",
                    "The common CSV term may differ from the "
                    "student's intended semester.",
                ],
            }

    return {
        "passed": False,
        "issues": [
            "No conflict-free combination could be verified. "
            "Sections may overlap or have missing, invalid, "
            "or ARRANGED meeting details."
        ],
        "selected_sections": [],
    }

