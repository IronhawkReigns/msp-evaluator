import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.requests import Request
import requests
from vector_writer import run_from_msp_name

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
    results = collection.get(include=["metadatas"])
    data = []
    for meta in results["metadatas"]:
        if question and question != meta["question"]:
            continue
        if meta["score"] is not None and int(meta["score"]) >= min_score:
            data.append({
                "msp_name": meta["msp_name"],
                "question": meta["question"],
                "score": meta["score"]
            })
    return JSONResponse(content=data)

@app.delete("/ui/delete/{entry_id}")
def delete_entry(entry_id: str):
    collection.delete(ids=[entry_id])
    return {"status": "success"}

@app.delete("/ui/delete_company/{company_name}")
def delete_company(company_name: str):
    results = collection.get(where={"msp_name": company_name})
    ids_to_delete = results["ids"]
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
    return {"status": "deleted", "count": len(ids_to_delete)}


# Query/Ask endpoint
@app.post("/query/ask")
async def ask_question(request: Request):
    from collections import defaultdict

    body = await request.json()
    question = body.get("question")
    min_score = int(body.get("min_score", 0))
    if not question:
        raise HTTPException(status_code=400, detail="Missing question")

    # Retrieve top 3 relevant chunks from ChromaDB
    try:
        query_results = collection.query(
            query_texts=[question],
            n_results=3
        )
        grouped_chunks = defaultdict(list)
        for meta in query_results["metadatas"][0]:
            if meta["score"] is not None and int(meta["score"]) >= min_score:
                grouped_chunks[meta["msp_name"]].append(f"Q: {meta['question']}\nA: {meta['answer']}")

        if not grouped_chunks:
            return {"answer": "해당 조건에 맞는 평가 데이터를 찾을 수 없습니다."}

        context_blocks = []
        for msp, qa_list in grouped_chunks.items():
            context_blocks.append(f"[{msp}]\n" + "\n".join(qa_list))

        context = "\n\n".join(context_blocks)
        prompt = (
            f"{context}\n\n"
            f"위의 MSP 후보들 중에서 '{question}' 기준으로 상위 3개 회사를 선정하고, 각각 그 이유를 설명해주세요. "
            f"응답 형식은 순위와 회사명, 간단한 설명으로 구성해주세요."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")

    # Call HyperCLOVA API (new style using OpenAI client)
    from openai import OpenAI
    CLOVA_API_KEY = os.getenv("CLOVA_API_KEY")
    API_URL = "https://clovastudio.stream.ntruss.com/v1/openai"
    client = OpenAI(api_key=CLOVA_API_KEY, base_url=API_URL)
    model = "HCX-005"

    import json
    try:
        clova_response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "정확하고 간결하게 답변해 주세요."},
                {"role": "user", "content": prompt}
            ],
            top_p=0.8,
            temperature=0.7,
            max_tokens=500
        )
        try:
            if not clova_response.choices or not clova_response.choices[0].message.content:
                print("⚠️ CLOVA 응답 없음 또는 content 필드 비어 있음")
                return {"answer": "CLOVA 응답을 처리할 수 없습니다. 다시 시도해주세요."}

            # 디버깅용 전체 응답 출력
            print("==== CLOVA RAW RESPONSE ====")
            print(json.dumps(clova_response.model_dump(), indent=2, ensure_ascii=False))

            answer = clova_response.choices[0].message.content.strip()
            return {"answer": answer}
        except Exception as e:
            print("❌ CLOVA 응답 처리 중 예외:", str(e))
            raise HTTPException(status_code=500, detail=f"응답 처리 실패: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HyperCLOVA error: {str(e)}")
