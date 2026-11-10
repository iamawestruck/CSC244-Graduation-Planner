
from pathlib import Path
import sys

import pandas as pd


def _project_root() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent if here.name in {"tools", "agents"} else here


PROJECT_ROOT = _project_root()
CSV_PATH = next(
    (
        candidate
        for candidate in (
        PROJECT_ROOT / "data" / "sac_state_courses.csv",
        PROJECT_ROOT / "sac_state_courses.csv",
    )
        if candidate.is_file()
    ),
    PROJECT_ROOT / "data" / "sac_state_courses.csv",
    )
CHROMA_PATH = PROJECT_ROOT / "school_courses"


def index_courses() -> int:
    if not CSV_PATH.is_file():
        print(f"Course CSV not found: {CSV_PATH}", file=sys.stderr)
        return 1

    try:
        from langchain_chroma import Chroma
        from langchain_core.documents import Document
        from langchain_ollama import OllamaEmbeddings
    except ImportError as exc:
        print(f"Missing indexing dependency: {exc}", file=sys.stderr)
        print("Install the project dependencies with: pip install -r requirements.txt", file=sys.stderr)
        return 1

    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
    needed = {"Subject", "Number", "Name", "Description", "Credit Hours", "Section Status"}
    missing = needed.difference(df.columns)
    if missing:
        print("Course CSV is missing columns: " + ", ".join(sorted(missing)), file=sys.stderr)
        return 1

    df = df[df["Section Status"].str.strip().str.upper().ne("SYNTHETIC - NOT REAL")]
    documents = []
    ids = []
    for _, row in df.drop_duplicates(subset=["Subject", "Number"]).iterrows():
        code = f"{row['Subject']} {row['Number']}".strip()
        documents.append(
            Document(
                page_content=(
                    f"Course: {code}\n"
                    f"Name: {row['Name']}\n"
                    f"Description: {row['Description']}\n"
                    f"Credit Hours: {row['Credit Hours']}\n"
                    f"Degree Attributes: {row.get('Degree Attributes', '')}\n"
                ),
                metadata={
                    "source": "csv",
                    "subject": str(row["Subject"]),
                    "number": str(row["Number"]),
                    "name": str(row["Name"]),
                },
            )
        )
        ids.append(code.replace(" ", "-"))

    try:
        store = Chroma(
            collection_name="sac_state_courses",
            embedding_function=OllamaEmbeddings(
                model="mxbai-embed-large",
                base_url="http://localhost:11434",
            ),
            persist_directory=str(CHROMA_PATH),
        )
        batch_size = 32
        for start in range(0, len(documents), batch_size):
            end = start + batch_size
            store.add_documents(documents[start:end], ids=ids[start:end])
            print(f"Indexed {min(end, len(documents))} / {len(documents)} courses")
    except Exception as exc:
        print(f"Course indexing failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("Check that Ollama is running and mxbai-embed-large is installed.", file=sys.stderr)
        return 1

    print(f"Added or updated {len(documents)} course records in {CHROMA_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(index_courses())

