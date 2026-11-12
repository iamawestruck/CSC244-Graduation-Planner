from pathlib import Path
import pandas as pd


def _project_root() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent if here.name in {"tools", "agents"} else here


PROJECT_ROOT = _project_root()
STUDENTS_CSV = next(
    (
        candidate
        for candidate in (
            PROJECT_ROOT / "data" / "sac_state_students.csv",
            PROJECT_ROOT / "sac_state_students.csv",
        )
        if candidate.is_file()
    ),
    PROJECT_ROOT / "data" / "sac_state_students.csv",
)


def load_student(student_id: str | None = None) -> dict[str, str]:
    """Load a profile by ID, or the only profile when the CSV has just one."""
    if not STUDENTS_CSV.is_file():
        raise FileNotFoundError(
            f"Student CSV not found at {STUDENTS_CSV}. Put it in the project root or data/ folder."
        )

    students = pd.read_csv(STUDENTS_CSV, dtype=str, keep_default_na=False)
    if "student_id" not in students.columns:
        raise ValueError("Student CSV must contain a 'student_id' column.")
    if students.empty:
        raise ValueError(f"No student profiles were found in {STUDENTS_CSV}.")

    if student_id is None or not str(student_id).strip():
        if len(students) != 1:
            available = ", ".join(students["student_id"].astype(str).tolist())
            raise ValueError(
                "Pass --student-id to choose a profile. Available IDs: " + available
            )
        return students.iloc[0].to_dict()

    selected_id = str(student_id).strip()
    matches = students[
        students["student_id"].astype(str).str.strip().eq(selected_id)
    ]
    if matches.empty:
        raise ValueError(f"Student ID {selected_id!r} not found.")
    if len(matches) > 1:
        raise ValueError(f"Student ID {selected_id!r} appears more than once.")
    return matches.iloc[0].to_dict()
