from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from vector_writer import run_from_msp_name
import os
import chromadb
from chromadb import PersistentClient

app = FastAPI()

class CompanyInput(BaseModel):
    name: str

@app.post("/run/{msp_name}")
def run_msp_vector_pipeline(msp_name: str):
    try:
        run_from_msp_name(msp_name)
        return {"message": f"Vector DB update completed for {msp_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/ui")
def serve_ui():
    return FileResponse("static/index.html")

# Load ChromaDB
CHROMA_PATH = os.path.abspath("chroma_store")
client = PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection("msp_chunks")

@app.get("/ui/data")
def get_all_chunks():
    results = collection.get(include=["metadatas"])
    data = []
    for meta in results["metadatas"]:
        data.append({
            "msp_name": meta["msp_name"],
            "question": meta["question"],
            "score": meta["score"]
        })
    return JSONResponse(content=data)
