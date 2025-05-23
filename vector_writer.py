import chromadb
import os
from dotenv import load_dotenv
load_dotenv()
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

import requests
import uuid

def chunk_text(text: str):
    CLOVA_SEGMENTATION_API_URL = "https://clovastudio.stream.ntruss.com/testapp/v1/api-tools/segmentation"
    HEADERS = {
        "Authorization": f"Bearer {os.getenv('CLOVA_API_KEY')}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": "20cc0852bff04af399b61a31980a6c48",
        "Content-Type": "application/json"
    }
    payload = {
        "postProcessMaxSize": 1000,
        "alpha": 0.0,
        "segCnt": -1,
        "postProcessMinSize": 300,
        "text": text,
        "postProcess": False
    }
    try:
        response = requests.post(CLOVA_SEGMENTATION_API_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["result"]["topicSeg"]
    except Exception as e:
        print(f"Error calling segmentation API: {e}")
        return [text]  # fallback: return original text as single chunk
from sheets_reader import INTERVIEW_SHEET_DOC_NAME, connect_to_sheets, get_company_data_from_sheet, get_summary_scores

# Initialize Chroma client and collection
CHROMA_PATH = os.path.abspath("chroma_store")
client = PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection("msp_chunks")

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

def add_msp_data_to_chroma(company_name, company_data, summary):
    documents = []
    embeddings = []
    metadatas = []
    ids = []

    for idx, (question, entry) in enumerate(company_data.items()):
        answer = entry["answer"]
        score = entry["score"]
        chunks = chunk_text(answer)
        for cidx, chunk in enumerate(chunks):
            document = f"Q: {question}\nA: {chunk}"
            embedding = model.encode(document)
            uid = f"{company_name}_{idx}_{cidx}"
            metadata = {
                "msp_name": company_name,
                "question": question,
                "answer": chunk,
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
