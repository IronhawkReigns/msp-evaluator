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
            n_results=10
        )
        grouped_chunks = defaultdict(list)
        for meta in query_results["metadatas"][0]:
            if meta["score"] is not None and int(meta["score"]) >= min_score:
                grouped_chunks[meta["msp_name"]].append(
                    f"Q: {meta['question']}\nA: {meta['answer']} (score: {meta['score']})"
                )

        if not grouped_chunks:
            return {"answer": "해당 조건에 맞는 평가 데이터를 찾을 수 없습니다."}

        context_blocks = []
        for msp, qa_list in grouped_chunks.items():
            context_blocks.append(f"[{msp}]\n" + "\n".join(qa_list))

        context = "\n\n".join(context_blocks)
        prompt = (
            f"{context}\n\n"
            f"위에 제공된 Q&A 정보만을 기반으로 '{question}'에 가장 잘 부합하는 *상위 2개* 회사를 선정해주세요.\n"
            f"결코 없는 정보를 추론하거나 일반적인 기대를 기반으로 답하지 마세요. 명확한 정보가 없는 경우, 해당 회사를 제외하세요.\n"
            f"각 Q&A 항목의 score는 질문과의 관련성을 나타내지만, 반드시 점수가 높다고 해서 해당 질문에 대한 직접적인 답변을 의미하지는 않습니다. \n\n"
            f"질문과의 명확한 연결고리를 중점적으로 평가하세요. 예를 들어, UI/UX 관련 질문이라면 '사용 편의성', '인터페이스', '접근성', '직관성' 등의 키워드가 포함된 응답이 가장 관련성이 높습니다. \n\n"
            f"보안, 성능, 데이터 처리 등은 유사 개념이지만 해당 질문에 직접적으로 답하지 않았다면 선정 근거로 사용하지 마세요.\n\n"
            f"절대로 없는 정보를 추론하거나 일반적인 기대를 바탕으로 점수를 부여하지 마세요.\n\n"
            f"응답은 다음 형식으로 작성해주세요:\n"
            f"회사명을 굵게 표시하고, 각 회사를 별도의 단락으로 설명해주세요. 예:\n\n"
            f"**A 회사**\n"
            f"- 선정 이유: AI 전문 인력 비율이 매우 높은 것으로 확인되고 해당 질문에서 5점을 받음\n\n"
            f"**B 회사**\n"
            f"- 선정 이유: OCR 특화 기술 및 현업 기반 평가 경험이 풍부하며 (5점) 실적과 협업 구조가 우수함 (4점)\n\n"
            f"**기타 회사**\n"
            f"- 선정 이유: 필요 시 명확한 증빙이 있는 경우에만 언급"
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
                print("CLOVA 응답 없음 또는 content 필드 비어 있음")
                answer = ""
            else:
                answer = clova_response.choices[0].message.content.strip()
            # Debug
            print("==== CLOVA RAW RESPONSE ====")
            print(json.dumps(clova_response.model_dump(), indent=2, ensure_ascii=False))
            return {"answer": answer or "", "raw": clova_response.model_dump()}
        except Exception as e:
            print("CLOVA 응답 처리 중 예외:", str(e))
            raise HTTPException(status_code=500, detail=f"응답 처리 실패: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HyperCLOVA error: {str(e)}")
