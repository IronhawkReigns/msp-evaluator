from msp_core import (
    run_msp_recommendation,
    run_msp_information_summary,
    run_msp_information_summary_claude,
    extract_msp_name,
    query_embed,
    collection,
)
from clova_router import Executor
from pydantic import BaseModel
from difflib import get_close_matches
import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, Depends, Request
class RouterQuery(BaseModel):
    query: str
    chat_history: list = []
    advanced: bool = False  # NEW
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
import requests
from vector_writer import run_from_msp_name
from admin_protected import router as admin_router, manager

# Register user_loader at import time to avoid "Missing user_loader callback" error
@manager.user_loader()
def load_user(username: str):
    from admin_protected import User
    env_username = os.getenv("ADMIN_USERNAME")
    if username == env_username:
        return User(name=username)

import chromadb
from chromadb import PersistentClient

app = FastAPI()

app.include_router(admin_router)
print("📦 admin router included")



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
def serve_ui(request: Request):
    try:
        user = manager(request)
        return FileResponse("static/index.html")
    except:
        return RedirectResponse(url="/login?next=/ui")


# Serve query UI
@app.get("/query")
def serve_query_ui():
    return FileResponse("static/query.html")

# Load ChromaDB
CHROMA_PATH = os.path.abspath("chroma_store")
client = PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection("msp_chunks")

@app.get("/ui/data")
def get_filtered_chunks(question: str = None, min_score: int = 0):
    # Return flat format for public UI compatibility
    results = collection.get(include=["metadatas"])
    data = []
    for meta in results["metadatas"]:
        if not isinstance(meta.get("answer"), str) or not meta["answer"].strip():
            continue
        if question and question != meta["question"]:
            continue
        if meta["score"] is not None and int(meta["score"]) >= min_score:
            data.append({
                "msp_name": meta["msp_name"],
                "question": meta["question"],
                "score": meta["score"],
                "answer": meta["answer"]
            })
    return JSONResponse(content=data)

# Flat data endpoint for public UI
@app.get("/ui/data_flat")
def get_flat_chunks(question: str = None, min_score: int = 0):
    results = collection.get(include=["metadatas"])
    data = []
    for meta in results["metadatas"]:
        if not isinstance(meta.get("answer"), str) or not meta["answer"].strip():
            continue
        if question and question != meta["question"]:
            continue
        if meta["score"] is not None and int(meta["score"]) >= min_score:
            data.append({
                "msp_name": meta["msp_name"],
                "question": meta["question"],
                "score": meta["score"],
                "answer": meta["answer"]
            })
    return JSONResponse(content=data)

# Query/Ask endpoint
@app.post("/query/ask")
async def ask_question(request: Request):
    body = await request.json()
    question = body.get("question")
    min_score = int(body.get("min_score", 0))
    if not question:
        raise HTTPException(status_code=400, detail="Missing question")

    return run_msp_recommendation(question, min_score)

# Router endpoint
@app.post("/query/router")
async def query_router(data: RouterQuery):
    print(f"🟢 Advanced toggle received: {data.advanced}")
    executor = Executor()
    request_data = {
        "query": data.query,
        "chatHistory": data.chat_history
    }
    raw_result = executor.execute(request_data)

    import json
    import traceback

    try:
        if isinstance(raw_result, str):
            result = json.loads(raw_result)
        else:
            result = raw_result

        domain_result = result.get("domain", {}).get("result")
        blocked = result.get("blockedContent", {}).get("result", [])

        if domain_result == "mspevaluator":
            extracted_name = extract_msp_name(data.query)
            print(f"🧠 CLOVA 추출 회사명: {extracted_name}")
            print(f"🟢 Advanced toggle received: {data.advanced}")
            if "Information" in blocked:
                if data.advanced:
                    return run_msp_information_summary_claude(data.query)
                else:
                    return run_msp_information_summary(data.query)
            elif "Recommend" in blocked:
                return run_msp_recommendation(data.query, min_score=0)
            elif "Unrelated" in blocked:
                return {"answer": "본 시스템은 MSP 평가 도구입니다. 해당 질문은 지원하지 않습니다. 다른 질문을 입력해 주세요."}
            else:
                return {"answer": "질문 의도를 정확히 분류하지 못했습니다. 다시 시도해 주세요."}
        else:
            return {"answer": "도메인 분류에 실패했습니다. 다시 시도해 주세요."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Router 처리 중 오류 발생: {str(e)}")

# Add protected /admin route using same login logic as /ui
@app.get("/admin")
def serve_admin_ui(request: Request):
    try:
        user = manager(request)
        return FileResponse("static/admin.html")
    except Exception as e:
        return RedirectResponse(url="/login?next=/admin")
    
@app.get("/")
def serve_main_page():
    return FileResponse("static/main.html")
