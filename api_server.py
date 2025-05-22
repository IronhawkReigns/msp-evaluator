from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from vector_writer import run_from_msp_name
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

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
    
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

from chromadb import PersistentClient

@app.get("/list_msp_entries")
def list_entries():
    client = PersistentClient(path="chroma_store")
    collection = client.get_or_create_collection("msp_chunks")
    results = collection.get(include=["metadatas"])

    entries = []
    for meta in results["metadatas"]:
        entries.append({
            "msp_name": meta.get("msp_name"),
            "question": meta.get("question"),
            "score": meta.get("score")
        })

    return entries
