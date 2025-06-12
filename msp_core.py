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
    Sophisticated MSP recommendation leveraging Claude's analytical capabilities
    """
    try:
        query_vector = query_embed(question)
        query_results = collection.query(
            query_embeddings=[query_vector],
            n_results=20  # Increased for more comprehensive analysis
        )
        
        grouped_chunks = defaultdict(list)
        for meta in query_results["metadatas"][0]:
            if not isinstance(meta.get("answer"), str) or not meta["answer"].strip():
                continue
            if meta["score"] is not None and int(meta["score"]) >= min_score:
                grouped_chunks[meta["msp_name"]].append({
                    "question": meta['question'],
                    "answer": meta['answer'],
                    "score": meta['score'],
                    "category": meta.get('category', '미분류'),
                    "group": meta.get('group', '기타')
                })

        if not grouped_chunks:
            return {"answer": "해당 조건에 맞는 평가 데이터를 찾을 수 없습니다."}

        # Advanced analytics for Claude's sophisticated analysis
        company_analytics = {}
        all_companies = list(grouped_chunks.keys())
        
        for msp, qa_list in grouped_chunks.items():
            scores = [qa['score'] for qa in qa_list]
            categories = defaultdict(list)
            
            # Organize by category for deeper analysis
            for qa in qa_list:
                categories[qa['category']].append(qa)
            
            # Calculate comprehensive metrics
            analytics = {
                'overall_avg': round(sum(scores) / len(scores), 2),
                'score_distribution': {
                    '5점': len([s for s in scores if s == 5]),
                    '4점': len([s for s in scores if s == 4]),
                    '3점': len([s for s in scores if s == 3]),
                    '2점 이하': len([s for s in scores if s <= 2])
                },
                'category_performance': {},
                'excellence_areas': [],
                'improvement_areas': [],
                'evidence_quality': {
                    'detailed_responses': len([qa for qa in qa_list if len(qa['answer']) > 150]),
                    'specific_examples': len([qa for qa in qa_list if any(keyword in qa['answer'].lower() 
                                            for keyword in ['프로젝트', '사례', '경험', '년', '개월', '%', '명', '건', '억', '만'])]),
                    'total_responses': len(qa_list)
                }
            }
            
            # Category-wise analysis
            for category, cat_qa_list in categories.items():
                if cat_qa_list:
                    cat_scores = [qa['score'] for qa in cat_qa_list]
                    analytics['category_performance'][category] = {
                        'avg_score': round(sum(cat_scores) / len(cat_scores), 2),
                        'response_count': len(cat_qa_list),
                        'excellence_count': len([s for s in cat_scores if s >= 4])
                    }
                    
                    # Identify excellence and improvement areas
                    cat_avg = sum(cat_scores) / len(cat_scores)
                    if cat_avg >= 4.0:
                        analytics['excellence_areas'].append(f"{category} ({cat_avg:.1f}점)")
                    elif cat_avg <= 3.0:
                        analytics['improvement_areas'].append(f"{category} ({cat_avg:.1f}점)")
            
            company_analytics[msp] = analytics

        # Create rich, structured context for Claude's analysis
        analysis_context = []
        
        for msp, qa_list in grouped_chunks.items():
            analytics = company_analytics[msp]
            
            # Best evidence selection - prioritize high scores and detailed answers
            sorted_qa = sorted(qa_list, key=lambda x: (x['score'], len(x['answer'])), reverse=True)
            top_evidence = sorted_qa[:6]  # Top 6 pieces of evidence
            
            company_block = f"""
=== {msp} 종합 분석 ===
전체 평균: {analytics['overall_avg']}/5점 | 응답 수: {analytics['evidence_quality']['total_responses']}개

점수 분포:
- 우수(5점): {analytics['score_distribution']['5점']}개
- 양호(4점): {analytics['score_distribution']['4점']}개  
- 보통(3점): {analytics['score_distribution']['3점']}개
- 미흡(2점 이하): {analytics['score_distribution']['2점 이하']}개

카테고리별 성과:
{chr(10).join([f"- {cat}: {perf['avg_score']:.1f}점 ({perf['response_count']}개 응답)" 
              for cat, perf in analytics['category_performance'].items()])}

강점 영역: {', '.join(analytics['excellence_areas']) if analytics['excellence_areas'] else '특이사항 없음'}
개선 영역: {', '.join(analytics['improvement_areas']) if analytics['improvement_areas'] else '특이사항 없음'}

구체성 지표:
- 상세 답변: {analytics['evidence_quality']['detailed_responses']}/{analytics['evidence_quality']['total_responses']}개
- 구체적 사례/수치: {analytics['evidence_quality']['specific_examples']}/{analytics['evidence_quality']['total_responses']}개

핵심 근거 자료:
{chr(10).join([f"[{qa['score']}점] {qa['category']} | Q: {qa['question'][:60]}{'...' if len(qa['question']) > 60 else ''}" + 
              f"{chr(10)}    A: {qa['answer'][:200]}{'...' if len(qa['answer']) > 200 else ''}"
              for qa in top_evidence])}
"""
            analysis_context.append(company_block)

        full_context = "\n".join(analysis_context)
        
        # Sophisticated prompt for Claude's analytical reasoning
        prompt = f"""당신은 15년 경력의 시니어 클라우드 컨설턴트로서, 다음 MSP 파트너사 평가 데이터를 종합 분석하여 최적의 추천을 제공해야 합니다.

사용자 요구사항: "{question}"

{full_context}

=== 전문가 분석 프레임워크 ===

1. **요구사항 적합성 분석**
   - 사용자 질문의 핵심 키워드와 각 회사의 관련 역량 매칭도
   - 단순 점수가 아닌 질문 맥락에서의 실제 적합성 평가

2. **역량 심화 분석**
   - 카테고리별 성과 패턴 및 균형성 검토
   - 우수 영역의 실질적 차별화 요소 식별
   - 약점 영역의 비즈니스 임팩트 평가

3. **증거 신뢰성 평가**
   - 답변의 구체성과 실무 경험 수준 판단
   - 정량적 데이터 vs 정성적 설명의 균형
   - 일관성 있는 전문성 입증 여부

4. **리스크 및 기회 요소**
   - 각 회사 선택 시 예상되는 이점과 제약사항
   - 프로젝트 성공 가능성과 잠재적 우려사항

5. **비교 우위 분석**
   - 회사 간 명확한 차별화 포인트
   - 동등한 수준일 경우의 세부 판단 기준

=== 응답 형식 (필수 준수) ===

**🏆 1순위 추천: [회사명]**
**적합도:** ⭐⭐⭐⭐⭐ (5/5)
**선정 근거:**
- [구체적 강점과 사용자 요구사항 연결점 2-3줄]
- [차별화 요소와 경쟁 우위 1-2줄]

**핵심 역량 분석:**
- 우수 분야: [카테고리] (X.X점) - [구체적 근거]
- 검증된 실적: [구체적 사례나 수치]

**선택 시 기대효과:** [실무적 관점의 이점]

---

**🥈 2순위 추천: [회사명]**  
**적합도:** ⭐⭐⭐⭐☆ (4/5)
**선정 근거:**
- [1순위와 차별화된 강점 설명]
- [특정 상황에서의 우위 요소]

**핵심 역량 분석:**
- 우수 분야: [카테고리] (X.X점) - [구체적 근거]
- 고려사항: [약점이나 제약사항이 있다면]

**선택 시 기대효과:** [실무적 관점의 이점]

---

**📊 종합 비교 분석**
- **핵심 차이점:** [1순위와 2순위의 명확한 구분점]
- **상황별 권장:** [어떤 상황에서 각각을 선택해야 하는지]

**신뢰도:** 높음 (분석 근거: 총 {sum(len(qa_list) for qa_list in grouped_chunks.values())}개 평가 데이터)

=== 분석 주의사항 ===
- 평가 점수는 참고용이며, 질문 맥락과의 실제 연관성을 우선 고려
- 구체적 근거가 있는 내용만 언급하며, 추측이나 일반론 금지
- 실무진이 의사결정에 활용할 수 있는 구체적이고 실행 가능한 인사이트 제공
- 회사명과 평가 데이터가 정확히 일치하는지 반드시 확인"""

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1200,  # Increased for comprehensive analysis
            temperature=0.1,   # Very low for consistent, analytical reasoning
            system="당신은 클라우드 및 MSP 선정 분야의 최고 수준 컨설턴트입니다. 데이터 기반의 논리적 분석과 실무적 통찰력을 겸비하여, 고객이 최적의 의사결정을 할 수 있도록 구조화되고 설득력 있는 추천을 제공합니다. 추상적 표현보다는 구체적 근거와 실질적 가치에 집중하며, 분석의 투명성과 신뢰성을 최우선으로 합니다.",
            messages=[{
                "role": "user", 
                "content": prompt
            }]
        )
        
        answer = response.content[0].text.strip()
        
        # Enhanced post-processing for consistency
        professional_terms = {
            "설루션": "솔루션",
            "구현": "구축", 
            "만들": "구축",
            "좋습니다": "우수합니다",
            "뛰어납니다": "우수합니다"
        }
        
        for old_term, new_term in professional_terms.items():
            answer = answer.replace(old_term, new_term)
        
        return {
            "answer": answer,
            "evidence": query_results["metadatas"][0],
            "model_used": "claude-3-haiku-expert-enhanced",
            "analysis_quality": "comprehensive_analytical",
            "companies_analyzed": len(grouped_chunks),
            "total_evidence_points": sum(len(qa_list) for qa_list in grouped_chunks.values()),
            "analytics_summary": {company: analytics['overall_avg'] for company, analytics in company_analytics.items()}
        }
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Claude API error: {str(e)}")

def run_msp_recommendation_clova(question: str, min_score: int):
    """
    Original CLOVA-based MSP recommendation function (backup)
    """
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
    """Direct Claude version without Perplexity"""
    import traceback
    
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
        prompt = f"""다음은 {best_match}에 대한 인터뷰 Q&A입니다:

{context}

사용자 질문: "{question}"

위 정보를 바탕으로 질문에 대해 정확하고 자연스럽게 답변해주세요. 주어진 정보에 없는 내용은 추론하지 마세요."""

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        
        answer = response.content[0].text.strip()
        answer = answer.replace("설루션", "솔루션")
        
        return {"answer": answer, "advanced": False, "evidence": filtered_chunks}
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Claude API error: {str(e)}")

def run_msp_information_summary_pplx(question: str):
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

def run_msp_news_summary_claude(question: str):
    """
    Enhanced version with more data for Claude
    """
    import urllib.parse
    import urllib.request
    import traceback
    import anthropic
    import os

    msp_name = extract_msp_name(question)
    if not msp_name:
        return {"answer": "회사명을 인식하지 못했습니다. 다시 시도해 주세요.", "advanced": True}

    # Enhanced vector DB search - get more relevant data for Claude
    try:
        query_vector = query_embed(question)
        query_results = collection.query(
            query_embeddings=[query_vector],
            n_results=15
        )
        db_chunks = [
            f"Q: {chunk['question']}\nA: {chunk['answer']} (점수: {chunk.get('score', 'N/A')}/5)"
            for chunk in query_results["metadatas"][0]
            if chunk.get("msp_name") == msp_name and chunk.get("question") and chunk.get("answer")
        ][:8]
        db_context = "\n\n".join(db_chunks)
    except Exception as e:
        db_context = ""

    try:
        # Enhanced API calls - get more comprehensive data
        query = urllib.parse.quote(msp_name)
        
        # Get more news articles for better coverage
        url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=15&sort=sim"
        headers = {
            "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID"),
            "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET")
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                raise Exception(f"Naver API Error: {response.status}")
            news_data = json.loads(response.read().decode("utf-8"))

        # Get more web documents for comprehensive view
        url_web = f"https://openapi.naver.com/v1/search/webkr.json?query={query}&display=7&sort=sim"
        req_web = urllib.request.Request(url_web, headers=headers)
        with urllib.request.urlopen(req_web) as response_web:
            if response_web.status != 200:
                raise Exception(f"Naver Web API Error: {response_web.status}")
            web_data = json.loads(response_web.read().decode("utf-8"))

        if "items" not in news_data or not news_data["items"]:
            return {"answer": f"{msp_name}에 대한 뉴스 기사를 찾을 수 없습니다.", "advanced": True}

        # Enhanced data cleaning and formatting for Claude
        def clean_text(text):
            return text.replace('<b>', '').replace('</b>', '').replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

        # Structured news formatting with more metadata
        news_items = []
        for i, item in enumerate(news_data["items"][:12], 1):  # Top 12 most relevant
            title = clean_text(item.get('title', ''))
            desc = clean_text(item.get('description', ''))
            pub_date = item.get('pubDate', '')[:10] if item.get('pubDate') else 'N/A'
            
            if title and desc:  # Only include substantial content
                news_items.append(f"{i}. [{pub_date}] {title}\n   세부내용: {desc}")

        # Structured web formatting with quality filtering
        web_items = []
        for i, item in enumerate(web_data.get("items", [])[:5], 1):  # Top 5 web docs
            title = clean_text(item.get('title', ''))
            desc = clean_text(item.get('description', ''))
            
            if title and desc and len(desc) > 50:  # Filter for substantial content
                web_items.append(f"{i}. {title}\n   요약: {desc}")

        article_text = "\n\n".join(news_items)
        web_text = "\n\n".join(web_items)

        # Enhanced prompt designed for Claude's analytical capabilities
        prompt = f"""다음은 클라우드 MSP 파트너사 '{msp_name}'에 대한 종합 정보입니다. 이 다양한 정보원을 분석하여 사용자 질문에 전문적이고 통찰력 있는 답변을 제공해주세요.

사용자 질문: "{question}"

=== 내부 평가 데이터 (가장 신뢰도 높음) ===
{db_context}

=== 뉴스 기사 정보 ({len(news_items)}개 최신 기사) ===
{article_text}

=== 웹 문서 정보 ({len(web_items)}개 관련 문서) ===
{web_text}

=== 전문가 수준 분석 지침 ===
1. **정보 통합 분석**: 내부 평가, 뉴스, 웹 정보를 종합하여 균형잡힌 시각 제공
2. **신뢰도 우선순위**: 내부 평가 데이터 → 공식 뉴스 → 웹 문서 순으로 가중치 적용
3. **구체적 근거 제시**: 
   - 평가 점수나 구체적 수치 우선 언급
   - 시기별 변화나 최근 동향 파악
   - 경쟁사 대비 차별화 요소 식별
4. **실무적 관점**: 실제 고객/파트너 관점에서 의미있는 정보 우선 정리
5. **객관적 균형**: 강점과 개선영역을 모두 고려한 공정한 평가

응답 형식: 자연스럽고 전문적인 한국어로 작성하되, 마케팅 표현보다는 팩트와 데이터 중심으로 서술해주세요."""

    except Exception as e:
        traceback.print_exc()
        return {"answer": f"뉴스 기반 요약에 실패했습니다: {str(e)}", "advanced": True}

    # Enhanced Claude API call with optimized parameters
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            temperature=0.2,  # Lower for more factual, analytical responses
            system="당신은 10년 이상 경력의 클라우드 및 MSP 전문 컨설턴트입니다. 다양한 정보원을 종합 분석하여 객관적이고 실용적인 통찰을 제공하며, 구체적 근거와 데이터에 기반한 전문가 수준의 평가를 중시합니다.",
            messages=[{
                "role": "user", 
                "content": prompt
            }]
        )
        
        answer = response.content[0].text.strip()
        
        # Enhanced post-processing for professional consistency
        answer = answer.replace("설루션", "솔루션")
        answer = answer.replace("클라우드 서비스", "클라우드 솔루션")
        
        return {
            "answer": answer, 
            "advanced": True, 
            "evidence": news_data["items"][:12], 
            "web_evidence": web_data.get("items", [])[:5],
            "model_used": "claude-3-haiku-enhanced",
            "data_summary": {
                "news_articles": len(news_items),
                "web_documents": len(web_items),
                "internal_qa_pairs": len(db_chunks),
                "total_sources": len(news_items) + len(web_items) + len(db_chunks)
            }
        }
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Claude API error: {str(e)}")
