import chromadb
import os
from dotenv import load_dotenv
load_dotenv()
from chromadb import PersistentClient
import requests
import uuid
from sheets_reader import INTERVIEW_SHEET_DOC_NAME, connect_to_sheets, get_company_data_from_sheet, get_summary_scores

# Initialize Chroma client and collection
CHROMA_PATH = os.path.abspath("chroma_store")
client = PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection("msp_chunks")

def add_msp_data_to_chroma(company_name, company_data, summary):
    documents = []
    embeddings = []
    metadatas = []
    ids = []

    for idx, (question, entry) in enumerate(company_data.items()):
        answer = entry["answer"]
        score = entry["score"]
        document = f"Q: {question}\nA: {answer}"
        embedding = get_clova_embedding(document)
        uid = f"{company_name}_{idx}"

        metadata = {
            "msp_name": company_name,
            "question": question,
            "answer": answer,
            "score": score,
            **summary
        }

        documents.append(document)
        embeddings.append(embedding)
        metadatas.append(metadata)
        ids.append(uid)

    collection.add(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )

def run_from_msp_name(company_name: str):
    print(f"Running vector DB update for: {company_name}")
    company_data = get_company_data_from_sheet(company_name)
    summary = get_summary_scores(company_name)
    add_msp_data_to_chroma(company_name, company_data, summary)
    print(f"{company_name} successfully written to ChromaDB.")

def get_clova_embedding(text):
    api_key = os.getenv("CLOVA_API_KEY")
    url = "https://clovastudio.stream.ntruss.com/v1/api-tools/embedding/v2/"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }
    data = {
        "text": text
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["result"]["embedding"]
    else:
        raise Exception(f"CLOVA embedding failed: {response.status_code} {response.text}")
