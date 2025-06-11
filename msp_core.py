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

import anthropic
import os
from collections import defaultdict
import traceback
from fastapi import HTTPException

def run_msp_recommendation(question: str, min_score: int):
    """
    Enhanced MSP recommendation using Claude instead of CLOVA
    """
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
                    f"Q: {meta['question']}\nA: {meta['answer']} (점수: {meta['score']}/5)"
                )

        if not grouped_chunks:
            return {"answer": "해당 조건에 맞는 평가 데이터를 찾을 수 없습니다."}

        context_blocks = []
        for msp, qa_list in grouped_chunks.items():
            context_blocks.append(f"[{msp}]\n" + "\n".join(qa_list))

        context = "\n\n".join(context_blocks)
        
        # Enhanced prompt for Claude
        prompt = f"""다음은 MSP 파트너사들의 평가 데이터입니다:

{context}

사용자 질문: "{question}"

위 데이터를 바탕으로 이 질문에 가장 적합한 상위 2개 MSP를 추천해주세요.

평가 기준:
1. 질문과의 직접적 관련성
2. 답변의 구체성과 상세함
3. 해당 영역의 평가 점수
4. 실제 경험과 역량 증명

응답 형식:
**1위 추천: [회사명]**
- 추천 이유: [구체적 근거 2-3문장]
- 핵심 강점: [주요 강점 요약]
- 관련 점수: [해당 영역 점수들]

**2위 추천: [회사명]**
- 추천 이유: [구체적 근거 2-3문장]  
- 핵심 강점: [주요 강점 요약]
- 관련 점수: [해당 영역 점수들]

주의사항:
- 주어진 데이터에 없는 내용은 추론하지 말 것
- 명확한 근거가 있는 경우에만 추천
- 점수보다는 답변 내용의 구체성을 우선시할 것"""

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")

    # Claude API call
    try:
        client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229", 
            max_tokens=1000,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        answer = response.content[0].text.strip()
        
        # Clean up common issues
        answer = answer.replace("설루션", "솔루션")
        
        return {
            "answer": answer,
            "evidence": query_results["metadatas"][0],
            "model_used": "claude-3-sonnet"
        }
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Claude API error: {str(e)}")
    
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

        CLOVA_API_KEY = os.getenv("CLOVA_API_KEY_OPENAI")
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
