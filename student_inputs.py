from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
STUDENTS_CSV = PROJECT_ROOT / "data" / "sac_state_students.csv"


def load_student(student_id: str) -> dict[str, str]:
    students = pd.read_csv(
        STUDENTS_CSV,
        dtype=str,
        keep_default_na=False,
    )

    matches = students[
        students["student_id"].astype(str).str.strip().eq(student_id.strip())
    ]
    if matches.empty:
        raise ValueError(f"Student ID {student_id!r} not found.")

    if len(matches) > 1:
        raise ValueError(f"Student ID {student_id!r} appears more than once.")

    return matches.iloc[0].to_dict()