import chromadb
import os
from dotenv import load_dotenv
load_dotenv()
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

import requests
import uuid
import http.client
import json

def chunk_text(text: str):
    text = text.strip()
    if not text:
        return []

    host = "clovastudio.stream.ntruss.com"
    request_id = str(uuid.uuid4().hex)
    api_key = f"Bearer {os.getenv('CLOVA_API_KEY')}"

    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': api_key,
        'X-NCP-CLOVASTUDIO-REQUEST-ID': request_id
    }

    completion_request = {
        "postProcessMaxSize": 1000,
        "alpha": 0.0,
        "segCnt": -1,
        "postProcessMinSize": 300,
        "text": text,
        "postProcess": False
    }

    try:
        conn = http.client.HTTPSConnection(host)
        conn.request('POST', '/testapp/v1/api-tools/segmentation', json.dumps(completion_request), headers)
        response = conn.getresponse()
        result = json.loads(response.read().decode(encoding='utf-8'))
        conn.close()

        if result["status"]["code"] == "20000":
            return [' '.join(segment) for segment in result["result"]["topicSeg"]]
        else:
            print(f"Segmentation API error: {result}")
            return [text]
    except Exception as e:
        print(f"Error calling segmentation API: {e}")
        return [text]
from sheets_reader import INTERVIEW_SHEET_DOC_NAME, connect_to_sheets, get_company_data_from_sheet, get_summary_scores

# Initialize Chroma client and collection
CHROMA_PATH = os.path.abspath("chroma_store")
client = PersistentClient(path=CHROMA_PATH)

# Set collection settings to expect 1024-dimension embeddings
from chromadb.config import Settings
from chromadb.utils import embedding_functions

collection = client.get_or_create_collection(
    name="msp_chunks",
    metadata={"hnsw:space": "cosine"},
    embedding_function=None,
)

# Load embedding model
def clova_embedding(text: str):
    host = "clovastudio.stream.ntruss.com"
    request_id = str(uuid.uuid4().hex)
    api_key = f"Bearer {os.getenv('CLOVA_API_KEY')}"

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": api_key,
        "X-NCP-CLOVASTUDIO-REQUEST-ID": request_id
    }

    body = json.dumps({ "text": text })
    conn = http.client.HTTPSConnection(host)
    conn.request("POST", "/testapp/v1/api-tools/embedding/v2/", body, headers)
    response = conn.getresponse()
    result = json.loads(response.read().decode("utf-8"))
    conn.close()

    if result["status"]["code"] == "20000":
        return result["result"]["embedding"]
    else:
        print(f"[Embedding API Error] {result}")
        return None

def add_msp_data_to_chroma(company_name, company_data, summary):
    documents = []
    embeddings = []
    metadatas = []
    ids = []

    # Print summary types for debugging
    print(f"Summary types for debugging: {[ (k, type(v)) for k, v in summary.items() ]}")
    for idx, (question, entry) in enumerate(company_data.items()):
        answer = entry["answer"]
        score = entry["score"]
        chunks = chunk_text(answer)
        for cidx, chunk in enumerate(chunks):
            document = f"Q: {question}\nA: {chunk}"
            embedding = clova_embedding(document)
            if not embedding:
                continue
            uid = f"{company_name}_{idx}_{cidx}"
            # Clean summary, log and skip problematic keys
            cleaned_summary = {}
            for k, v in summary.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    cleaned_summary[k] = v
                else:
                    print(f"[Metadata Error] Key '{k}' has invalid type {type(v)}. Value: {v}")
                    # Optionally: cleaned_summary[k] = str(v)

            metadata = {
                "msp_name": company_name,
                "question": question,
                "answer": chunk,
                "score": score,
                **cleaned_summary
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
    try:
        company_data = get_company_data_from_sheet(company_name)
        print("Fetched company data")
        summary = get_summary_scores(company_name)
        print("Fetched summary scores")
        add_msp_data_to_chroma(company_name, company_data, summary)
        print(f"{company_name} successfully written to ChromaDB.")
    except Exception as e:
        import traceback
        print(f"Error occurred while processing {company_name}")
        traceback.print_exc()
        raise
