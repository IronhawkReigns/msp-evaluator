from msp_core import (
    run_msp_recommendation,
    run_msp_information_summary,
    run_msp_information_summary_claude,
    extract_msp_name,
    query_embed,
    collection,
    run_msp_news_summary_clova
)
from fastapi import File, UploadFile
from excel_upload_handler import evaluate_uploaded_excel, compute_category_scores_from_excel_data, summarize_answers_for_subcategories
from clova_router import Executor
from pydantic import BaseModel
from difflib import get_close_matches
import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
import io
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


# Advanced Naver route
@app.post("/query/advanced_naver")
async def query_advanced_naver(data: RouterQuery):
    return run_msp_news_summary_clova(data.query)

# Add protected /admin route using same login logic as /ui
@app.get("/admin")
def serve_admin_ui(request: Request):
    try:
        user = manager(request)
        return FileResponse("static/admin.html")
    except Exception as e:
        return RedirectResponse(url="/login?next=/admin")


# Serve main page at root
@app.get("/")
def serve_main_page():
    return FileResponse("static/main.html")



# Serve upload page
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
templates = Jinja2Templates(directory="templates")

@app.get("/upload", response_class=HTMLResponse)
async def serve_upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

# Excel upload endpoint
from fastapi import UploadFile, File

@app.post("/api/upload_excel")
async def upload_excel(file: UploadFile = File(...)):
    try:
        from excel_upload_handler import evaluate_uploaded_excel, compute_category_scores_from_excel_data

        evaluated = evaluate_uploaded_excel(file)
        summary_df = compute_category_scores_from_excel_data(evaluated)

        flat_results = []
        skipped_items = []
        for category_name, qa_list in evaluated.items():
            if not isinstance(qa_list, list):
                skipped_items.append({
                    "category": category_name,
                    "item": qa_list,
                    "reason": f"Expected a list but got: {type(qa_list)}"
                })
                continue
            for item in qa_list:
                if not isinstance(item, dict) or "question" not in item or "answer" not in item or "score" not in item:
                    skipped_items.append({
                        "category": category_name,
                        "item": item,
                        "reason": "Missing required keys or invalid format"
                    })
                    continue
                flat_results.append({
                    "category": category_name,
                    "question": item["question"],
                    "answer": item["answer"],
                    "score": item["score"]
                })

        from collections import defaultdict
        group_scores = defaultdict(list)

        for item in flat_results:
            group = item.get("group", item.get("category"))
            score = item.get("score")
            if isinstance(score, (int, float)):
                group_scores[group].append(score)

        group_summary = []
        for group, scores in group_scores.items():
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0
            group_summary.append({
                "name": group,
                "score": avg_score,
                "questions": len(scores)
            })

        return JSONResponse(content={
            "evaluated_questions": flat_results,
            "summary": summary_df.to_dict(orient="records"),
            "skipped_items": skipped_items,
            "groups": group_summary
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Excel 평가 처리 중 오류 발생: {str(e)}")


# New endpoint: /api/get_summary
from fastapi import Request
@app.post("/api/get_summary")
async def get_summary(request: Request):
    try:
        data = await request.json()
        evaluated = data.get("evaluated")
        if evaluated is None:
            raise HTTPException(status_code=400, detail="Missing 'evaluated' data")

        # Group by category
        grouped = {}
        for item in evaluated:
            category = item.get("category", "Unknown")
            grouped.setdefault(category, []).append(item)

        from excel_upload_handler import summarize_answers_for_subcategories
        summary = summarize_answers_for_subcategories(grouped)
        return JSONResponse(content={"subcategory_summaries": summary})
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Summary processing failed: {str(e)}")

@app.post("/api/add_to_vector_db")
async def add_to_vector_db(data: dict):
    try:
        from vector_writer import run_from_direct_input
        msp_name = data.get("msp_name")
        if not msp_name:
            raise HTTPException(status_code=400, detail="Missing msp_name")

        items = data.get("items", [])
        if not isinstance(items, list):
            raise HTTPException(status_code=400, detail="Missing or invalid items list")

        summary = data.get("summary")
        if summary is None:
            raise HTTPException(status_code=400, detail="Missing summary")

        run_from_direct_input(msp_name, items, summary)
        return {"message": f"Successfully added {len(items)} items to vector DB for {msp_name}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Vector DB update failed: {str(e)}")
