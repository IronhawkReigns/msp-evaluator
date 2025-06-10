import chromadb
import os
import datetime
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
        conn.request('POST', '/serviceapp/v1/api-tools/segmentation', json.dumps(completion_request), headers)
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
    conn.request("POST", "/serviceapp/v1/api-tools/embedding/v2", body, headers)
    response = conn.getresponse()
    try:
        result = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[Embedding API Error] Failed to parse JSON response: {e}")
        conn.close()
        return []
    conn.close()

    if isinstance(result, dict) and result.get("status", {}).get("code") == "20000":
        embedding = result.get("result", {}).get("embedding")
        if embedding and isinstance(embedding, list):
            return embedding
        else:
            print(f"[Embedding API Error] Unexpected embedding format: {embedding}")
            return []
    else:
        print(f"[Embedding API Error] {result}")
        return []

# Add this function to your vector_writer.py

def add_msp_data_to_chroma(company_name, company_data, summary):
    documents = []
    embeddings = []
    metadatas = []
    ids = []

    # Create category mapping from groups to main categories
    category_mapping = {}
    
    # Extract category information from summary
    main_categories = ["인적역량", "AI기술역량", "솔루션 역량"]
    
    # If company_data has group information, map it to main categories
    if isinstance(company_data, list):
        for item in company_data:
            group = item.get('group', '').strip()
            if group and group not in category_mapping:
                # Try to match group to main category based on common patterns
                for main_cat in main_categories:
                    # You might need to adjust this logic based on your actual group names
                    if any(keyword in group for keyword in main_cat.split()):
                        category_mapping[group] = main_cat
                        break
                else:
                    # Default mapping - you might need to customize this
                    category_mapping[group] = "기타"

    print(f"[DEBUG] Category mapping for {company_name}: {category_mapping}")

    # Process summary to get category scores
    category_scores = {}
    if isinstance(summary, list):
        for item in summary:
            if isinstance(item, dict):
                cat_name = item.get('Category', '').strip()
                score = item.get('Score')
                if cat_name in main_categories and score is not None:
                    try:
                        # Convert percentage back to 1-5 scale
                        category_scores[cat_name] = float(score) / 20.0  # 100% scale to 5-point scale
                    except (ValueError, TypeError):
                        pass

    print(f"[DEBUG] Category scores for {company_name}: {category_scores}")

    # Process each data item
    for idx, entry in enumerate(company_data):
        question = entry.get('question', '')
        answer = entry.get("answer", "")
        score = entry.get("score", 0)
        group = entry.get('group', '').strip()
        
        # Map group to main category
        main_category = category_mapping.get(group, "기타")
        
        chunks = chunk_text(answer)
        for cidx, chunk in enumerate(chunks):
            document = f"Q: {question}\nA: {chunk}"
            embedding = clova_embedding(document)
            if not embedding:
                continue
            
            uid = f"{company_name}_{idx}_{cidx}"
            
            # Create metadata with proper category mapping
            metadata = {
                "msp_name": company_name,
                "question": question,
                "answer": chunk,
                "score": score,
                "group": group,  # Keep original group
                "category": main_category,  # Add mapped main category
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            
            # Add category scores to metadata
            for cat_name, cat_score in category_scores.items():
                metadata[f"{cat_name}_score"] = cat_score
            
            documents.append(document)
            embeddings.append(embedding)
            metadatas.append(metadata)
            ids.append(uid)

    if documents:  # Only add if we have documents
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[SUCCESS] Added {len(documents)} chunks for {company_name}")
    else:
        print(f"[WARNING] No documents to add for {company_name}")

# Also update the run_from_direct_input function
def run_from_direct_input(company_name: str, company_data: list, summary: list):
    print(f"Running vector DB update (direct input) for: {company_name}")
    try:
        add_msp_data_to_chroma(company_name, company_data, summary)
        print(f"{company_name} successfully written to ChromaDB.")
    except Exception as e:
        import traceback
        print(f"Error occurred while processing {company_name}")
        traceback.print_exc()
        raise

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
