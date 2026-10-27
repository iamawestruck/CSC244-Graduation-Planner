
from pathlib import Path
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
import pandas as pd
from crewai.tools import tool

# Resolve the CSV path relative to this file's project.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "uiuc_courses.csv"

# Set up the embedding model used to search the vector database
embeddings = OllamaEmbeddings(
    model="mxbai-embed-large",
    base_url="http://localhost:11434"
)

# Connect to the existing ChromaDB collection
vector_store = Chroma(
    collection_name="school_courses",
    embedding_function=embeddings,
    persist_directory=str(PROJECT_ROOT / "school_courses")
)

# Load the historical catalog once when this module is imported.
courses = pd.read_csv(CSV_PATH, dtype={"Subject": str, "Number": str})

# Keep one record per subject/course number for basic course lookup.
course_catalog = courses.drop_duplicates(
    subset=["Subject", "Number"]
).copy()


@tool("Retrieve courses from vector database")
def retrieve_courses(query: str) -> str:
    """Search the indexed course catalog by meaning and topic.
    Use this tool to retrieve course descriptions and details
    relevant to a student's academic interests or requirements."""

    results = vector_store.similarity_search(
        query=query,
        k=8
    )

    if not results:
        return "No relevant courses found in the vector database."

    course_results = []

    for doc in results:
        course_results.append(doc.page_content)

    return "\n\n---\n\n".join(course_results)

@tool("Search UIUC course catalog")
def search_courses(query: str) -> str:
    """Search Fall 2019 UIUC courses by course name or description.
    Use this to find courses matching a subject or topic."""

    name_matches = course_catalog["Name"].fillna("").str.contains(
        query, case=False, na=False, regex=False
    )
    description_matches = course_catalog["Description"].fillna("").str.contains(
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

    return matches[columns].head(20).to_string(index=False)


@tool("Get UIUC course details")
def get_course(subject: str, number: str) -> str:
    """Look up a specific course using its department and course number.
    Returns its name, credit hours, description, and degree attributes."""

    matches = course_catalog[
        course_catalog["Subject"].str.upper().eq(subject.strip().upper())
        & course_catalog["Number"].str.strip().eq(number.strip())
    ]

    if matches.empty:
        return f"Course {subject.upper()} {number} not found."

    row = matches.iloc[0]

    return (
        f"Catalog period: Fall 2019\n"
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
    planned_credit_hours: int,) -> str:
    """Compare planned and completed course codes against a
    student-provided list of required courses and minimum
    credit hours. Course lists must be comma-separated codes,
    such as CS 101, MATH 221."""

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
            "Required courses not accounted for: "
            + ", ".join(missing)
        )
    else:
        issues.append(
            "All supplied required course codes are "
            "accounted for in the plan or completed courses."
        )

    if planned_credit_hours < minimum_credits:
        issues.append(
            f"Credit shortfall: {minimum_credits - planned_credit_hours} "
            "additional planned credit hours needed."
        )
    else:
        issues.append(
            "The planned credit hours meet the supplied minimum."
        )

    return (
        "REQUIREMENT CHECK RESULTS\n"
        f"Required courses accounted for: "
        f"{', '.join(satisfied) or 'None'}\n"
        f"Missing required courses: {', '.join(missing) or 'None'}\n"
        f"Planned credit hours: {planned_credit_hours}\n"
        f"Minimum credit hours: {minimum_credits}\n"
        + "\n".join(issues)
        + "\n\nLimitations: This check only evaluates the "
        "requirements supplied as inputs. It does not verify "
        "prerequisites, course availability, elective rules, "
        "or official graduation eligibility."
    )
