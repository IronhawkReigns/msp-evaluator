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

def query_embed(text: str):
    from vector_writer import clova_embedding
    return clova_embedding(text)

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
        print(f"Meta object: {meta}")  # Log the metadata object
        answer = meta.get("answer", "")
        print(f"Answer type: {type(answer)}, value: {answer}")  # Debug output

        if question and question != meta["question"]:
            continue
        if not isinstance(answer, str) or not answer.strip():
            continue
        if meta["score"] is not None and int(meta["score"]) >= min_score:
            data.append({
                "msp_name": meta["msp_name"],
                "question": meta["question"],
                "score": meta["score"],
                "answer": answer
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
    import traceback
    try:
        query_vector = query_embed(question)
        query_results = collection.query(
            query_embeddings=[query_vector],
            n_results=10
        )
        grouped_chunks = defaultdict(list)
        for meta in query_results["metadatas"][0]:
            if not isinstance(meta.get("answer"), str) or not meta["answer"].strip():
                continue
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
            f"위의 Q&A 정보만을 바탕으로 '{question}'에 가장 잘 부합하는 상위 2개 회사를 선정해 주세요.\n\n"
            
            f"[주의사항]\n"
            f"- 추론 금지: 주어진 정보에 명확히 나타나지 않은 내용은 절대 추정하거나 일반적인 기대를 바탕으로 판단하지 마세요.\n"
            f"- 정보 부족 시 해당 회사를 제외하고, 명확한 연결고리가 있는 경우에만 선정하세요.\n"
            f"- score는 질문과의 관련성을 나타내는 보조 지표일 뿐이며, 반드시 높은 점수가 직접적인 답변을 의미하지는 않습니다.\n\n"

            f"[평가 기준]\n"
            f"1. 질문에 명시적으로 답하고 있는가?\n"
            f"2. 관련 핵심 키워드가 포함되어 있는가?\n"
            f"3. 구체적인 수치, 사례, 근거가 있는가?\n"
            f"4. 점수는 보조적으로만 사용하고, 응답 내용의 명확성을 중심으로 평가할 것\n"
            f"   예: 'UI/UX' 관련 질문의 경우 '사용 편의성', '인터페이스', '접근성', '직관성' 등 키워드 포함 여부 확인\n\n"

            f"[제외 기준]\n"
            f"- 보안, 성능, 데이터 처리 등 유사 개념은 질문에 직접적으로 답하지 않는 한 제외\n"
            f"- 추측, 기대 기반 해석, 점수만을 근거로 한 선정은 금지\n"
            f"- DB에 존재하지 않는 기업을 선정하는 것은 절대 금지\n\n"

            f"[응답 형식]\n"
            f"- 각 회사명을 **굵게** 표시하고, 각 회사를 별도의 단락으로 구성하세요.\n"
            f"- 최종 응답 전 회사명이 msp_name이 맞는지 확실히 확인 후 응답해 주세요.\n"
            f"- 선정 이유는 간결하고 명확하게 1~2문장으로 기술하세요.\n\n"

            f"예시:\n"
            f"**A 회사**\n"
            f"- 선정 이유: AI 전문 인력 비율이 높고, 해당 질문에 대해 구체적인 수치와 프로젝트 사례를 언급하며 5점을 받음\n\n"
            f"**B 회사**\n"
            f"- 선정 이유: OCR 기술 관련 경험을 보유하고 있으며, 해당 질문에 명확히 응답하고 4점을 기록함\n\n"
            f"**기타 회사**\n"
            f"- 관련 키워드 부재, 질문에 대한 직접적 답변 없음 등 명확한 근거가 있는 경우에만 간단히 언급"
        )
    except Exception as e:
        print("=== Vector search failed ===")
        traceback.print_exc()
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
            top_p=0.6,
            temperature=0.3,
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
