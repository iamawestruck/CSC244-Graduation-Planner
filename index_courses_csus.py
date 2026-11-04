from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import pandas as pd

embeddings = OllamaEmbeddings(model = "mxbai-embed-large", base_url="http://localhost:11434") #need to type "ollama pull mxbai-embed-large" to get to work
vector_store = Chroma(
    collection_name="school_courses",
    embedding_function=embeddings,
    persist_directory="./school_courses"
)

df = pd.read_csv("C:/Users/eharr/CSC244 Semester Project/graduation_planner/data/uiuc_courses.csv").fillna("")
df = df.drop_duplicates( subset=["Subject", "Number", "Name", "Description", "Start Time"])

csv_list = df.to_dict(orient="records")

csv_docs = [Document(
    page_content=(            
        f"Course: {doc['Subject']} {doc['Number']}\n"
        f"Name: {doc['Name']}\n"
        f"Description: {doc['Description']}\n"
        f"Credit Hours: {doc['Credit Hours']}\n"
        f"Degree Attributes: {doc['Degree Attributes']}\n"
        f"Year: {doc['Year']}\n"
        f"Term: {doc['Term']}\n"
        f"Days: {doc['Days of Week']}\n"
        f"Time: {doc['Start Time']} to {doc['End Time']}"), 
    metadata={
        "source": "csv",
        "subject": str(doc["Subject"]),
        "number": str(doc["Number"]),
        "name": str(doc["Name"]),
        "year": str(doc["Year"]),
        "term": str(doc["Term"]),
        "days": str(doc['Days of Week']),
        "start_time": str(doc["Start Time"]),
        "end_time": str(doc["End Time"])
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