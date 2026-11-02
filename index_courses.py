from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import pandas as pd
from pathlib import Path
embeddings = OllamaEmbeddings(model = "mxbai-embed-large", base_url="http://localhost:11434") #need to type "ollama pull mxbai-embed-large" to get to work
PROJECT_ROOT = Path(__file__).resolve().parent
CSV_PATH = PROJECT_ROOT / "data" / "sac_state_courses.csv"
CHROMA_PATH = PROJECT_ROOT / "school_courses"
vector_store = Chroma(
    collection_name="sac_state_courses",
    embedding_function=embeddings,
    persist_directory=str(CHROMA_PATH),
)

df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
df = df[df["Section Status"] != "SYNTHETIC - NOT REAL"]
csv_list = df.to_dict(orient="records")

csv_docs = [Document(
    page_content=(            
        f"Course: {doc['Subject']} {doc['Number']}\n"
        f"Name: {doc['Name']}\n"
        f"Description: {doc['Description']}\n"
        f"Credit Hours: {doc['Credit Hours']}\n"
        f"Degree Attributes: {doc['Degree Attributes']}\n"),
    metadata={
        "source": "csv",
        "subject": str(doc["Subject"]),
        "number": str(doc["Number"]),
        "name": str(doc["Name"])
    }
)for doc in csv_list]



ids = [str(i) for i in range(len(csv_docs))]

batch_size = 10 # needed to use batch size because it couldn't handle loading 7520 courses at once

for start in range(0, len(csv_docs), batch_size):
    end = start + batch_size

    vector_store.add_documents(
        documents=csv_docs[start:end],
        ids=ids[start:end]
    )

    print(f"Indexed {min(end, len(csv_docs))} / {len(csv_docs)} courses")

print(f"Added {len(csv_docs)} course records to ChromaDB.")

# results = vector_store.similarity_search(
#     "courses related to machine learning",
#     k=5
# )

# for doc in results:
#     print(doc.page_content)
#     print("---")