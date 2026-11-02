from pathlib import Path

import pandas as pd
from crewai.tools import tool
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings


# Paths are relative to the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "sac_state_courses.csv"
CHROMA_PATH = PROJECT_ROOT / "school_courses"

embeddings = OllamaEmbeddings(
    model="mxbai-embed-large",
    base_url="http://localhost:11434",
)

# Connect to the collection created by index_courses.py.
vector_store = Chroma(
    collection_name="sac_state_courses",
    embedding_function=embeddings,
    persist_directory=str(CHROMA_PATH),
)

# Keep the full CSV for schedule checks.
courses = pd.read_csv(
    CSV_PATH,
    dtype=str,
    keep_default_na=False,
)

# Exclude synthetic sections from catalog search and course lookup.
course_catalog = (
    courses.loc[
        courses["Section Status"]
        .astype(str)
        .str.strip()
        .str.upper()
        .ne("SYNTHETIC - NOT REAL")
    ]
        .drop_duplicates(subset=["Subject", "Number"])
        .copy()
)


@tool("Retrieve courses from vector database")
def retrieve_courses(query: str) -> str:
    """Search indexed Sacramento State courses by topic or meaning."""

    results = vector_store.similarity_search(query=query, k=8)

    if not results:
        return "No relevant courses found in the vector database."

    return "\n\n---\n\n".join(doc.page_content for doc in results)


@tool("Search Sacramento State course catalog")
def search_courses(query: str) -> str:
    """Search Sacramento State courses by name or description."""

    name_matches = course_catalog["Name"].str.contains(
        query, case=False, na=False, regex=False
    )
    description_matches = course_catalog["Description"].str.contains(
        query, case=False, na=False, regex=False
    )

    matches = course_catalog[name_matches | description_matches]

    if matches.empty:
        return f"No courses found matching '{query}'."

    columns = [
        "Subject",
        "Number",
        "Name",
        "Credit Hours",
        "Description",
    ]

    short_results = matches[columns].head(5).copy()
    short_results["Description"] = short_results["Description"].str.slice(0, 350)

    return short_results.to_string(index=False)


@tool("Get Sacramento State course details")
def get_course(subject: str, number: str) -> str:
    """Look up a course by department and course number."""

    subject_key = subject.strip().upper()
    number_key = str(number).strip().upper()

    matches = course_catalog[
        course_catalog["Subject"].str.strip().str.upper().eq(subject_key)
        & course_catalog["Number"].str.strip().str.upper().eq(number_key)
        ]

    if matches.empty:
        return f"Course {subject_key} {number_key} not found."

    row = matches.iloc[0]

    return (
        "Catalog: Sacramento State\n"
        f"Course: {row['Subject']} {row['Number']}\n"
        f"Name: {row['Name']}\n"
        f"Credit Hours: {row['Credit Hours']}\n"
        f"Degree Attributes: {row['Degree Attributes']}\n"
        f"Description: {row['Description']}"
    )


@tool("Check graduation requirements")
def check_user_requirements(
        required_courses: str,
        planned_courses: str,
        completed_courses: str,
        minimum_credits: int,
        planned_credit_hours: int,
) -> str:
    """Compare course codes and planned credits against student-provided requirements."""

    def parse_courses(course_text: str) -> set[str]:
        return {
            " ".join(course.strip().upper().split())
            for course in course_text.split(",")
            if course.strip()
        }

    required = parse_courses(required_courses)
    planned = parse_courses(planned_courses)
    completed = parse_courses(completed_courses)

    missing = sorted(required - planned - completed)
    satisfied = sorted(required & (planned | completed))

    issues = []

    if missing:
        issues.append(
            "Required courses not accounted for: " + ", ".join(missing)
        )
    else:
        issues.append(
            "All supplied required course codes are accounted for "
            "in the plan or completed courses."
        )

    if planned_credit_hours < minimum_credits:
        issues.append(
            f"Credit shortfall: {minimum_credits - planned_credit_hours} "
            "additional planned credit hours needed."
        )
    else:
        issues.append("The planned credit hours meet the supplied minimum.")

    return (
            "REQUIREMENT CHECK RESULTS\n"
            f"Required courses accounted for: {', '.join(satisfied) or 'None'}\n"
            f"Missing required courses: {', '.join(missing) or 'None'}\n"
            f"Planned credit hours: {planned_credit_hours}\n"
            f"Minimum credit hours: {minimum_credits}\n"
            + "\n".join(issues)
            + "\n\nLimitations: This check evaluates only requirements supplied "
              "as inputs. It does not verify prerequisites, course availability, "
              "elective rules, or official graduation eligibility."
    )