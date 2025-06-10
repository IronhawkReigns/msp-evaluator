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
import json

group_to_category_cache = {}

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

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to your React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

        print(f"[DEBUG] summary_df.columns: {summary_df.columns.tolist()}")

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
            if category_name == "summary":
                continue
            for item in qa_list:
                if (
                    not isinstance(item, dict)
                    or not item.get("question")
                    or not item.get("answer")
                    or item.get("score") is None
                ):
                    skipped_items.append({
                        "category": category_name,
                        "item": item,
                        "reason": "Missing required keys, empty fields, or invalid format"
                    })
                    continue
                flat_results.append({
                    "category": category_name,
                    "question": item["question"],
                    "answer": item["answer"],
                    "score": item["score"],
                    "group": item.get("group")  # Preserve group info for summary
                })

        from collections import defaultdict
        # Build group to question count mapping, with group key stripped
        group_to_questions = defaultdict(list)
        for q in flat_results:
            group_key = q["group"]
            if isinstance(group_key, str):
                group_key = group_key.strip()
            group_to_questions[group_key].append(q)

        group_question_counts = {group: len(questions) for group, questions in group_to_questions.items()}

        # Filter from summary_df instead of recomputing
        group_summary = []
        for record in summary_df.to_dict(orient="records"):
            print(f"[DEBUG] Summary Record: {record}")
            name = record.get("Category")
            score = record.get("Score")
            # Ensure name is a string and strip whitespace
            if not isinstance(name, str):
                continue
            name = name.strip()
            print(f"[DEBUG] ➕ Group Summary Item Candidate - name: {name}, score: {score}")
            if "총점" in name:
                continue
            try:
                score = float(score)
            except (ValueError, TypeError):
                continue
            group_summary.append({
                "name": name,
                "score": score,
                "questions": group_question_counts.get(name, 0)
            })
            print(f"[DEBUG] Added group summary item: name={name}, score={score}")

        print(f"[DEBUG] Final Group Summary Payload: {group_summary}")

        group_to_category = {}

        # The category_name in evaluated dict comes from sheet names
        for category_name, qa_list in evaluated.items():
            if not isinstance(qa_list, list):
                continue
            if category_name == "summary":
                continue
            
            # The category_name here is the parent category (sheet name)
            parent_category = category_name
            
            # Map all groups found in this sheet to the parent category
            seen_groups = set()
            for item in qa_list:
                group = item.get("group")
                if group and isinstance(group, str):
                    group = group.strip()
                    if group not in seen_groups:
                        group_to_category[group] = parent_category
                        seen_groups.add(group)
            
            # Also map the parent category to itself
            group_to_category[parent_category] = parent_category

        print(f"[DEBUG] Dynamic group_to_category mapping: {json.dumps(group_to_category, ensure_ascii=False, indent=2)}")

        return JSONResponse(content={
            "evaluated_questions": flat_results,
            "summary": summary_df.to_dict(orient="records"),
            "skipped_items": skipped_items,
            "groups": group_summary,  # THIS IS ALREADY HERE - just make sure it's used
            "group_to_category": group_to_category
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

        # Debug: print evaluated
        print(f"[DEBUG] Received evaluated (len={len(evaluated)}): {evaluated}")

        # Group by group field (fallback to category if missing)
        grouped = {}
        for item in evaluated:
            group = item.get("group") or item.get("category") or "Unknown"
            grouped.setdefault(group, []).append(item)

        # Debug: print grouped keys
        print(f"[DEBUG] Grouped keys: {list(grouped.keys())}")

        from excel_upload_handler import summarize_answers_for_subcategories
        # Debug: entering summarize
        print("[DEBUG] Entering summarize_answers_for_subcategories")
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

@app.get("/api/get_radar_data")
async def get_radar_data():
    try:
        # Return empty data since we're not using global variable anymore
        # Frontend should use the data from upload response instead
        return JSONResponse(content={})
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Radar data failed: {str(e)}")

@app.get("/api/get_group_to_category_map")
async def get_group_to_category_map():
    try:
        # Directly return the cached mapping built during upload
        from fastapi.responses import JSONResponse
        global group_to_category_cache
        if not group_to_category_cache:
            raise HTTPException(status_code=404, detail="Group-to-category map not available yet. Upload data first.")
        return JSONResponse(content=group_to_category_cache)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Group-to-category map failed: {str(e)}")

# Replace your existing /api/leaderboard endpoint in api_server.py with this safer version:

@app.get("/api/leaderboard")
async def get_leaderboard():
    try:
        # Fetch all metadata from ChromaDB
        results = collection.get(include=["metadatas"])
        msp_aggregates = {}

        # First pass: collect all data per MSP
        for meta in results["metadatas"]:
            msp_name = meta.get("msp_name")
            score = meta.get("score")
            
            if not msp_name or score is None:
                continue

            if msp_name not in msp_aggregates:
                msp_aggregates[msp_name] = {
                    "name": msp_name,
                    "scores": [],
                    "groups": {}
                }

            # Add score to total
            msp_aggregates[msp_name]["scores"].append(score)
            
            # Try to get group information for category mapping
            group = meta.get("group") or meta.get("category") or "Unknown"
            if group not in msp_aggregates[msp_name]["groups"]:
                msp_aggregates[msp_name]["groups"][group] = []
            msp_aggregates[msp_name]["groups"][group].append(score)

        # Second pass: calculate averages and map to main categories
        leaderboard = []
        main_categories = ["인적역량", "AI기술역량", "솔루션 역량"]
        
        # Group mapping - customize this based on your actual group names
        group_to_category_mapping = {
            # Human resources related
            "AI 전문 인력 구성": "인적역량",
            "프로젝트 경험 및 성공 사례": "인적역량", 
            "지속적인 교육 및 학습": "인적역량",
            "프로젝트 관리 및 커뮤니케이션": "인적역량",
            "AI 윤리 및 책임 의식": "인적역량",
            
            # AI Technology related
            "AI 기술 연구 능력": "AI기술역량",
            "AI 모델 개발 능력": "AI기술역량",
            "AI 플랫폼 및 인프라 구축 능력": "AI기술역량", 
            "데이터 처리 및 분석 능력": "AI기술역량",
            "AI 기술의 융합 및 활용 능력": "AI기술역량",
            "AI 기술의 특허 및 인증 보유 현황": "AI기술역량",
            
            # Solution related
            "다양성 및 전문성": "솔루션 역량",
            "안정성": "솔루션 역량", 
            "확장성 및 유연성": "솔루션 역량",
            "사용자 편의성": "솔루션 역량",
            "보안성": "솔루션 역량",
            "기술 지원 및 유지보수": "솔루션 역량",
            "차별성 및 경쟁력": "솔루션 역량",
            "개발 로드맵 및 향후 계획": "솔루션 역량"
        }

        for msp_name, data in msp_aggregates.items():
            # Calculate total average
            total_avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            
            # Calculate category averages
            category_scores = {}
            for main_cat in main_categories:
                category_score_list = []
                
                # Collect scores from groups that belong to this main category
                for group_name, group_scores in data["groups"].items():
                    if group_name in group_to_category_mapping:
                        if group_to_category_mapping[group_name] == main_cat:
                            category_score_list.extend(group_scores)
                    # Fallback: if group name contains category keywords
                    elif any(keyword in group_name for keyword in main_cat.split()):
                        category_score_list.extend(group_scores)
                
                # Calculate average for this category
                if category_score_list:
                    category_scores[main_cat] = sum(category_score_list) / len(category_score_list)
                else:
                    category_scores[main_cat] = 0

            leaderboard.append({
                "name": msp_name,
                "total_score": round(total_avg, 2),
                "category_scores": {k: round(v, 2) for k, v in category_scores.items()}
            })

        # Sort by total score (descending)
        leaderboard.sort(key=lambda x: x["total_score"], reverse=True)
        
        # Debug logging
        print(f"[DEBUG] Generated leaderboard for {len(leaderboard)} MSPs:")
        for msp in leaderboard[:3]:
            print(f"[DEBUG] {msp['name']}: Total={msp['total_score']}, Categories={msp['category_scores']}")
        
        return JSONResponse(content=leaderboard)

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Leaderboard generation failed: {str(e)}")


# Also add this debug endpoint to help you understand your current data structure:
@app.get("/api/debug_groups")
async def debug_groups():
    """Debug endpoint to see what groups/categories exist in your data"""
    try:
        results = collection.get(include=["metadatas"])
        
        groups_by_msp = {}
        all_groups = set()
        
        for meta in results["metadatas"]:
            msp_name = meta.get("msp_name")
            group = meta.get("group") or meta.get("category") or "Unknown"
            
            if msp_name:
                if msp_name not in groups_by_msp:
                    groups_by_msp[msp_name] = set()
                groups_by_msp[msp_name].add(group)
                all_groups.add(group)
        
        # Convert sets to lists for JSON serialization
        groups_by_msp = {k: list(v) for k, v in groups_by_msp.items()}
        
        return {
            "all_unique_groups": sorted(list(all_groups)),
            "groups_by_msp": groups_by_msp,
            "total_msps": len(groups_by_msp)
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")
