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

    if not value or value == "ARRANGED":
        return None

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

            if not days or start is None or end is None or start >= end:
                continue

            options.append({
                "days": days,
                "start": start,
                "end": end,
                "display": (
                    f"{row['Subject']} {row['Number']} "
                    f"Section {row.get('Section', '')}: "
                    f"{row['Days of Week']} "
                    f"{row['Start Time']}-{row['End Time']}"
                ),
            })

        return options

    def overlaps(section_a, section_b):
        shared_days = section_a["days"] & section_b["days"]
        return bool(shared_days) and (
                section_a["start"] < section_b["end"]
                and section_b["start"] < section_a["end"]
        )

    for term in sorted(common_terms):
        options_by_course = {
            code: get_options(rows, term)
            for code, rows in course_rows.items()
        }

        if any(not options for options in options_by_course.values()):
            continue

        ordered_courses = sorted(
            options_by_course,
            key=lambda code: len(options_by_course[code]),
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
                ],
            }

    return {
        "passed": False,
        "issues": [
            "No conflict-free combination of sections with known meeting "
            "days and times was found."
        ],
        "selected_sections": [],
    }