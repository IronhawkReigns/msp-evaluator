from fpdf import FPDF
from datetime import datetime
from fastapi import HTTPException
from typing import Any
import requests
import json
import uuid
from difflib import get_close_matches
from vector_writer import clova_embedding
import os
import chromadb
from chromadb import PersistentClient

# Embedding and collection setup
def query_embed(text: str):
    return clova_embedding(text)

CHROMA_PATH = os.path.abspath("chroma_store")
client = PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection("msp_chunks")

def run_msp_recommendation(question: str, min_score: int):
    from collections import defaultdict
    import traceback
    from openai import OpenAI
    import json

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
            f"- score는 질문과의 관련성을 나타내는 보조 지표일 뿐이며, 반드시 높은 점수가 직접적인 답변을 의미하지는 않습니다.\n"
            f"- 맞춤법과 문법에 유의하여 오타 없이 작성할 것\n\n"
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
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")

    CLOVA_API_KEY = os.getenv("CLOVA_API_KEY_OPENAI")
    API_URL = "https://clovastudio.stream.ntruss.com/v1/openai"
    client = OpenAI(api_key=CLOVA_API_KEY, base_url=API_URL)
    model = "HCX-005"

    try:
        clova_response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "클라우드 전문가 수준의 문장으로, 오탈자 없이 정확한 맞춤법과 문법을 사용해 주세요. 문장은 간결하면서도 자연스럽고, 일관되며 신뢰감 있게 작성해 주세요."},
                {"role": "user", "content": prompt}
            ],
            top_p=0.6,
            temperature=0.3,
            max_tokens=500
        )
        if not clova_response.choices or not clova_response.choices[0].message.content:
            answer = ""
        else:
            answer = clova_response.choices[0].message.content.strip()
        answer = answer.replace("설루션", "솔루션")
        return {"answer": answer, "raw": clova_response.model_dump(), "evidence": query_results["metadatas"][0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HyperCLOVA error: {str(e)}")
    
# Information summary function (for Information domain)
def run_msp_information_summary(question: str):
    import traceback
    from openai import OpenAI
    import json

    query = question
    msp_name = extract_msp_name(question)

    all_results = collection.get(include=["metadatas"])
    all_msp_names = [meta.get("msp_name", "") for meta in all_results["metadatas"] if meta.get("msp_name")]

    matches = get_close_matches(msp_name, all_msp_names, n=1, cutoff=0.6)
    if not matches:
        return {"answer": "질문하신 회사명을 인식하지 못했습니다. 다시 시도해 주세요.", "advanced": False}
    best_match = matches[0]

    try:
        query_vector = query_embed(question)
        query_results = collection.query(
            query_embeddings=[query_vector],
            n_results=8
        )
        filtered_chunks = [c for c in query_results["metadatas"][0] if c.get("answer") and c.get("question") and c.get("msp_name") == best_match]
        if not filtered_chunks:
            return {"answer": "관련된 정보를 찾을 수 없습니다.", "advanced": False}

        answer_blocks = []
        for chunk in filtered_chunks:
            if not chunk.get("answer") or not chunk.get("question"):
                continue
            answer_blocks.append(f"Q: {chunk['question']}\nA: {chunk['answer']}")

        context = "\n\n".join(answer_blocks)
        prompt = (
            f"다음은 MSP 파트너사 관련 인터뷰 Q&A 모음입니다. 아래 내용을 바탕으로 사용자 질문에 대해 응답해 주세요.\n"
            f"사용자 질문: \"{question}\"\n\n"
            f"{context}\n\n"
            f"[응답 지침]\n"
            f"- 실제 Q&A에 기반해 요약하거나 종합적으로 정리해 주세요.\n"
            f"- 없는 정보를 추론하거나 꾸며내지 마세요.\n"
            f"- 질문과 다른 타 회사의 정보를 절대로 억지로 끼워맞추지 마세요."
            f"- 가능한 한 간결하면서도 신뢰도 있는 표현으로 작성해 주세요.\n"
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")

    CLOVA_API_KEY = os.getenv("CLOVA_API_KEY_OPENAI")
    API_URL = "https://clovastudio.stream.ntruss.com/v1/openai"
    client = OpenAI(api_key=CLOVA_API_KEY, base_url=API_URL)
    model = "HCX-005"

    try:
        clova_response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "정확한 정보에 기반한 자연스러운 응답을 해주세요. 오탈자 없이 명확하고 일관된 문장으로 작성해 주세요."},
                {"role": "user", "content": prompt}
            ],
            top_p=0.6,
            temperature=0.3,
            max_tokens=500
        )
        if not clova_response.choices or not clova_response.choices[0].message.content:
            answer = ""
        else:
            answer = clova_response.choices[0].message.content.strip()
        answer = answer.replace("설루션", "솔루션")
        return {"answer": answer, "raw": clova_response.model_dump(), "advanced": False, "evidence": filtered_chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HyperCLOVA error: {str(e)}")

def run_msp_information_summary_claude(question: str):
    import traceback
    import requests
    import os

    query = question
    msp_name = extract_msp_name(question)

    all_results = collection.get(include=["metadatas"])
    all_msp_names = [meta.get("msp_name", "") for meta in all_results["metadatas"] if meta.get("msp_name")]

    from difflib import get_close_matches
    matches = get_close_matches(msp_name, all_msp_names, n=1, cutoff=0.6)
    if not matches:
        return {"answer": "질문하신 회사명을 인식하지 못했습니다. 다시 시도해 주세요.", "advanced": True}
    best_match = matches[0]

    try:
        query_vector = query_embed(question)
        query_results = collection.query(
            query_embeddings=[query_vector],
            n_results=8
        )
        filtered_chunks = [c for c in query_results["metadatas"][0] if c.get("answer") and c.get("question") and c.get("msp_name") == best_match]
        if not filtered_chunks:
            return {"answer": "관련된 정보를 찾을 수 없습니다.", "advanced": True}

        answer_blocks = []
        for chunk in filtered_chunks:
            if not chunk.get("answer") or not chunk.get("question"):
                continue
            answer_blocks.append(f"Q: {chunk['question']}\nA: {chunk['answer']}")

        context = "\n\n".join(answer_blocks)
        prompt = (
            f"{context}\n\n"
            f"사용자의 질문은 다음과 같습니다:\n"
            f"\"{question}\"\n\n"
            f"[응답 가이드라인]\n"
            f"- 아래 Q&A는 참고용일 뿐이며, 더 정확하거나 풍부한 정보가 있다면 웹 기반의 지식도 자유롭게 활용해 주세요.\n"
            f"- 근거가 명확한 경우, 주어진 정보 외의 배경지식도 적극 활용해 주세요.\n"
            f"- 문장은 자연스럽고 신뢰감 있게 작성해 주세요.\n"
            f"- 지나치게 형식을 강조하기보다는, 명확하고 유익한 정보를 중심으로 서술해 주세요.\n"
            f"- 회사명은 명확히 언급하되, 반복을 피하고 문맥에 자연스럽게 녹여 주세요."
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")

    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('PPLX_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [
                    {"role": "system", "content": "정확하고 신뢰할 수 있는 정보를 간결한 한국어로 제공하세요."},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )
        print(f"🔎 Claude API status: {response.status_code}")
        print(f"📦 Claude API raw response: {response.text}")
        if response.status_code == 200:
            import re
            result = response.json()
            answer = result["choices"][0]["message"]["content"].strip()
            # Clean up answer
            answer = re.sub(r"\[Q&A\]", "", answer)
            answer = re.sub(r"Q[:：]", "", answer)
            answer = re.sub(r"A[:：]", "", answer)
            answer = answer.strip()
            answer = re.sub(r"\[\d+\]", "", answer)  # Remove [1], [2], etc.
            return {"answer": answer, "advanced": True, "evidence": filtered_chunks}
        else:
            return {"answer": "Claude API 호출에 실패했습니다.", "advanced": True}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Claude API error: {str(e)}")

def extract_msp_name(question: str) -> str:
    from openai import OpenAI
    import os

    CLOVA_API_KEY = os.getenv("CLOVA_API_KEY_OPENAI")
    API_URL = "https://clovastudio.stream.ntruss.com/v1/openai"
    client = OpenAI(api_key=CLOVA_API_KEY, base_url=API_URL)
    model = "HCX-005"

    prompt = (
        f"다음 질문에서 실제 클라우드 MSP 파트너사의 이름만 정확하게 추출하세요. 문장 전체를 출력하지 말고, 회사명만 출력하세요.\n"
        f"[예시]\n"
        f"질문: 'ITCEN CLOIT에 대해 알려줘'\n응답: ITCEN CLOIT\n"
        f"질문: 'Lomin의 AI 역량은?'\n응답: Lomin\n"
        f"질문: '베스핀글로벌의 MLOps 사례는?'\n응답: 베스핀글로벌\n"
        f"질문: '{question}'\n"
        f"응답:"
    )

    try:
        clova_response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "질문에서 클라우드 MSP 회사 이름만 정확하게 추출해 주세요. 문장은 절대 작성하지 말고, 회사명만 단독으로 출력하세요. 예: 베스핀글로벌"},
                {"role": "user", "content": prompt}
            ],
            top_p=0.6,
            temperature=0.3,
            max_tokens=20
        )
        raw = clova_response.choices[0].message.content.strip()
        print(f"🔍 Extracted raw MSP name: {raw}")
        return raw
    except Exception as e:
        print(f"❌ Error extracting MSP name: {e}")
        return ""

def run_msp_news_summary_clova(question: str):
    import urllib.parse
    import urllib.request
    import traceback

    msp_name = extract_msp_name(question)
    if not msp_name:
        return {"answer": "회사명을 인식하지 못했습니다. 다시 시도해 주세요.", "advanced": True}

    # Get vector DB information for the MSP
    try:
        query_vector = query_embed(question)
        query_results = collection.query(
            query_embeddings=[query_vector],
            n_results=10
        )
        db_chunks = [
            f"Q: {chunk['question']}\nA: {chunk['answer']}"
            for chunk in query_results["metadatas"][0]
            if chunk.get("msp_name") == msp_name and chunk.get("question") and chunk.get("answer")
        ][:5]
        db_context = "\n\n".join(db_chunks)
    except Exception as e:
        db_context = ""

    try:
        query = urllib.parse.quote(msp_name)
        url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=10&sort=sim"
        headers = {
            "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID"),
            "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET")
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                raise Exception(f"Naver API Error: {response.status}")
            news_data = json.loads(response.read().decode("utf-8"))

        url_web = f"https://openapi.naver.com/v1/search/webkr.json?query={query}&display=3&sort=sim"
        req_web = urllib.request.Request(url_web, headers=headers)
        with urllib.request.urlopen(req_web) as response_web:
            if response_web.status != 200:
                raise Exception(f"Naver Web API Error: {response_web.status}")
            web_data = json.loads(response_web.read().decode("utf-8"))

        if "items" not in news_data or not news_data["items"]:
            return {"answer": f"{msp_name}에 대한 뉴스 기사를 찾을 수 없습니다.", "advanced": True}

        article_summaries = "\n".join(
            f"- 제목: {item['title'].replace('<b>', '').replace('</b>', '')}\n  요약: {item['description'].replace('<b>', '').replace('</b>', '')}"
            for item in news_data["items"]
        )

        web_summaries = "\n".join(
            f"- 제목: {item['title'].replace('<b>', '').replace('</b>', '')}\n  요약: {item['description'].replace('<b>', '').replace('</b>', '')}"
            for item in web_data.get("items", [])
        )

        prompt = (
            f"다음은 클라우드 MSP 기업 '{msp_name}'에 대한 뉴스 기사, 웹 문서, 인터뷰 Q&A 요약입니다. 이 내용을 바탕으로 사용자의 질문에 응답해 주세요.\n"
            f"사용자 질문: \"{question}\"\n\n"
            f"[DB 기반 정보]\n{db_context}\n\n"
            f"[뉴스 기사 요약]\n{article_summaries}\n\n"
            f"[웹 문서 요약]\n{web_summaries}\n\n"
            f"[응답 지침]\n"
            f"- 기사, 웹 문서, 인터뷰 Q&A 내용을 기반으로 응답을 생성하세요.\n"
            f"- 없는 정보를 꾸며내거나 추론하지 마세요.\n"
            f"- 기업의 수상 실적, 협업, 투자, 인력 구성 등 핵심 정보를 간결하게 요약해 주세요."
        )

        CLOVA_API_KEY = os.getenv("CLOVA_API_KEY")
        API_URL = "https://clovastudio.stream.ntruss.com/v1/openai"
        from openai import OpenAI
        client = OpenAI(api_key=CLOVA_API_KEY, base_url=API_URL)
        model = "HCX-005"

        clova_response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "정확하고 신뢰할 수 있는 응답을 자연스럽고 간결한 문장으로 작성해 주세요."},
                {"role": "user", "content": prompt}
            ],
            top_p=0.6,
            temperature=0.3,
            max_tokens=500
        )
        answer = clova_response.choices[0].message.content.strip()
        answer = answer.replace("설루션", "솔루션")
        return {"answer": answer, "advanced": True, "evidence": news_data["items"], "web_evidence": web_data.get("items", [])}
    except Exception as e:
        traceback.print_exc()
        return {"answer": f"뉴스 기반 요약에 실패했습니다: {str(e)}", "advanced": True}
