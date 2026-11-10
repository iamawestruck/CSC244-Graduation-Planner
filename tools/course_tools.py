import re
from pathlib import Path

import pandas as pd


try:
    from crewai.tools import tool
except ImportError:
    # Keep catalog search and the smoke script usable before CrewAI is installed.
    def tool(name):
        def decorate(function):
            function.name = name
            function.run = function
            return function

        return decorate


def _project_root() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent if here.name in {"tools", "agents"} else here


PROJECT_ROOT = _project_root()
CSV_NAME = "sac_state_courses.csv"
CSV_PATH = next(
    (
        candidate
        for candidate in (
        PROJECT_ROOT / "data" / CSV_NAME,
        PROJECT_ROOT / CSV_NAME,
    )
        if candidate.is_file()
    ),
    PROJECT_ROOT / "data" / CSV_NAME,
    )
CHROMA_PATH = PROJECT_ROOT / "school_courses"

if not CSV_PATH.is_file():
    raise FileNotFoundError(
        f"Course CSV not found at {CSV_PATH}. Put it in the project root or data/ folder."
    )

courses = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
required_columns = {
    "Subject",
    "Number",
    "Name",
    "Description",
    "Credit Hours",
    "Prerequisites",
    "Requirement Group",
    "Term Typically Offered",
    "Section Status",
}
missing_columns = required_columns.difference(courses.columns)
if missing_columns:
    raise ValueError(
        "The course CSV is missing these columns: "
        + ", ".join(sorted(missing_columns))
    )

# Keep synthetic section rows for schedule demonstrations, but exclude them
# from course catalog searches and graduation-plan candidates.
course_catalog = (
    courses.loc[
        courses["Section Status"].str.strip().str.upper().ne("SYNTHETIC - NOT REAL")
    ]
    .drop_duplicates(subset=["Subject", "Number"])
    .copy()
    .reset_index(drop=True)
)

vector_store = None
vector_store_error = None
try:
    from langchain_chroma import Chroma
    from langchain_ollama import OllamaEmbeddings

    # Some uploaded projects store Chroma directly in the project root.
    chroma_path = (
        PROJECT_ROOT
        if (PROJECT_ROOT / "chroma.sqlite3").is_file()
        else CHROMA_PATH
    )
    embeddings = OllamaEmbeddings(
        model="mxbai-embed-large",
        base_url="http://localhost:11434",
    )
    vector_store = Chroma(
        collection_name="sac_state_courses",
        embedding_function=embeddings,
        persist_directory=str(chroma_path),
    )
except Exception as exc:
    # A vector DB is optional for the planner; the CSV catalog remains usable.
    vector_store_error = exc


def _course_code_matches(query: str):
    return re.fullmatch(r"\s*([A-Z]{2,5})\s+(\d+[A-Z]*)\s*", query, re.I)


@tool("Retrieve Sacramento State courses by topic")
def retrieve_courses(query: str) -> str:
    """Find Sacramento State course records related to a topic or interest."""
    query = str(query or "").strip()
    if not query:
        return "Enter a topic or interest to search for."
    if vector_store is None:
        return (
            "Topic search is unavailable because the vector-search dependencies "
            "or database are not ready. Exact catalog search is still available."
        )

    try:
        results = vector_store.similarity_search(query=query, k=8)
    except Exception as exc:
        return f"Vector search is unavailable: {exc}"

    if not results:
        return "No relevant Sacramento State courses were found in the vector database."
    return "\n\n---\n\n".join(doc.page_content for doc in results)


@tool("Search Sacramento State course catalog")
def search_courses(query: str) -> str:
    """Search Sacramento State course names, descriptions, or exact course codes."""
    query = str(query or "").strip()
    if not query:
        return "Enter a course code, name, or topic to search for."

    code_match = _course_code_matches(query)
    if code_match:
        subject, number = code_match.groups()
        matches = course_catalog[
            course_catalog["Subject"].str.strip().str.upper().eq(subject.upper())
            & course_catalog["Number"].str.strip().str.upper().eq(number.upper())
            ]
    else:
        name_matches = course_catalog["Name"].str.contains(
            query, case=False, na=False, regex=False
        )
        description_matches = course_catalog["Description"].str.contains(
            query, case=False, na=False, regex=False
        )
        matches = course_catalog[name_matches | description_matches]

    if matches.empty:
        return f"No Sacramento State courses found matching '{query}'."

    columns = [
        "Subject",
        "Number",
        "Name",
        "Credit Hours",
        "Prerequisites",
        "Requirement Group",
        "Term Typically Offered",
    ]
    return matches[columns].head(10).to_string(index=False)


@tool("Get Sacramento State course details")
def get_course(subject: str, number: str) -> str:
    """Look up one Sacramento State course by subject and number."""
    subject = str(subject or "").strip().upper()
    number = str(number or "").strip().upper()
    matches = course_catalog[
        course_catalog["Subject"].str.strip().str.upper().eq(subject)
        & course_catalog["Number"].str.strip().str.upper().eq(number)
        ]

    if matches.empty:
        return f"No Sacramento State course found for {subject} {number}."

    columns = [
        "Subject",
        "Number",
        "Name",
        "Description",
        "Credit Hours",
        "Prerequisites",
        "Requirement Group",
        "Term Typically Offered",
    ]
    return matches.iloc[0][columns].to_string()


@tool("Check student-supplied graduation requirements")
def check_user_requirements(
        required_courses: str,
        completed_courses: str = "",
        planned_courses: str = "",
        minimum_credits: int = 0,
        planned_credits: int = 0,
) -> str:
    """Compare supplied course codes and credit totals with a draft plan."""

    def parse_codes(value: str) -> set[str]:
        return {
            " ".join(code.strip().upper().split())
            for code in str(value or "").split(",")
            if code.strip()
        }

    required = parse_codes(required_courses)
    completed = parse_codes(completed_courses)
    planned = parse_codes(planned_courses)
    outstanding = required - completed
    missing = sorted(outstanding - planned)
    findings = []

    if missing:
        findings.append("Missing supplied required courses: " + ", ".join(missing))
    elif outstanding:
        findings.append("All supplied unfinished required courses are in the plan.")
    else:
        findings.append("No unfinished supplied required courses remain.")

    if minimum_credits and planned_credits < minimum_credits:
        findings.append(
            f"Planned credits ({planned_credits}) are below the supplied minimum "
            f"({minimum_credits})."
        )
    elif minimum_credits:
        findings.append(
            f"Planned credits ({planned_credits}) meet the supplied minimum "
            f"({minimum_credits})."
        )

    return "\n".join(findings)
