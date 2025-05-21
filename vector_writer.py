import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from sheets_reader import INTERVIEW_SHEET_DOC_NAME, connect_to_sheets, get_company_data_from_sheet, get_summary_scores

# Initialize Chroma client and collection
client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory="./chroma_store"))
collection = client.get_or_create_collection("msp_chunks")

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

def add_msp_data_to_chroma(company_name, company_data, summary):
    for question, entry in company_data.items():
        answer = entry["answer"]
        score = entry["score"]
        document = f"Q: {question}\nA: {answer}"
        embedding = model.encode(document)
        uid = f"{company_name}_{hash(question)}"

        metadata = {
            "msp_name": company_name,
            "question": question,
            "answer": answer,
            "score": score,
            **summary
        }

        collection.add(
            documents=[document],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[uid]
        )

def run_from_msp_name(company_name: str):
    print(f"Running vector DB update for: {company_name}")
    company_data = get_company_data_from_sheet(company_name)
    summary = get_summary_scores(company_name)
    add_msp_data_to_chroma(company_name, company_data, summary)
    print(f"{company_name} successfully written to ChromaDB.")
