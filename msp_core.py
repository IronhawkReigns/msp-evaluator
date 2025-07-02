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
            n_results=20
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

        # Enhanced analytics for comprehensive reasoning
        company_analytics = {}
        all_companies = list(grouped_chunks.keys())
        
        for msp, qa_list in grouped_chunks.items():
            scores = [qa['score'] for qa in qa_list]
            categories = defaultdict(list)
            
            for qa in qa_list:
                categories[qa['category']].append(qa)
            
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
            
            for category, cat_qa_list in categories.items():
                if cat_qa_list:
                    cat_scores = [qa['score'] for qa in cat_qa_list]
                    analytics['category_performance'][category] = {
                        'avg_score': round(sum(cat_scores) / len(cat_scores), 2),
                        'response_count': len(cat_qa_list),
                        'excellence_count': len([s for s in cat_scores if s >= 4])
                    }
                    
                    cat_avg = sum(cat_scores) / len(cat_scores)
                    if cat_avg >= 4.0:
                        analytics['excellence_areas'].append(f"{category} ({cat_avg:.1f}점)")
                    elif cat_avg <= 3.0:
                        analytics['improvement_areas'].append(f"{category} ({cat_avg:.1f}점)")
            
            company_analytics[msp] = analytics

        # Create rich context for Claude's reasoning
        analysis_context = []
        
        for msp, qa_list in grouped_chunks.items():
            analytics = company_analytics[msp]
            sorted_qa = sorted(qa_list, key=lambda x: (x['score'], len(x['answer'])), reverse=True)
            top_evidence = sorted_qa[:6]
            
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
        
        # Enhanced prompt focused on targeted recommendation with clear reasoning
        prompt = f"""당신은 MSP 전문가입니다. 다음 평가 데이터를 바탕으로 사용자 요구사항에 맞는 회사를 추천해주세요.

사용자 요구사항: "{question}"

{full_context}

=== 핵심 임무 ===
주어진 평가 데이터에서 사용자 질문에 **직접 관련된** 역량을 가진 회사들을 찾아 추천하되, 
**왜 그 회사들을 선택했는지**와 **어떤 순서로 우선순위를 매겼는지** 명확히 설명하세요.

=== 추천 과정 ===

**1단계: 요구사항 식별**
사용자 질문에서 핵심 키워드와 요구사항을 추출:
- 기술 분야: [AI, 클라우드, 보안, 데이터 등]
- 특수 조건: [정부, 대규모, 특정 산업 등]
- 중요도: [필수 vs 선호 요구사항]

**2단계: 관련 회사 선별**
각 회사의 평가 데이터에서 질문과 **직접 관련된** 증거만 검토:
- 해당 기술/분야의 구체적 경험이 있는가?
- 관련 질문에 대해 상세하고 설득력 있는 답변을 했는가?
- 평가 점수가 요구사항 대비 적절한가?

**3단계: 우선순위 결정**
선별된 회사들 간 순위를 정하는 기준:
- 요구사항과의 직접적 부합도
- 구체적 사례와 경험의 풍부함
- 평가 점수의 우수성
- 답변의 신뢰성과 구체성

=== 응답 형식 ===

**[요구사항 분석]**
핵심 요구사항: [사용자가 찾는 것이 무엇인지]
중요 키워드: [질문에서 추출한 기술/조건 키워드들]

**[추천 결과]**

**1순위: [회사명]**
**선정 이유:** [이 회사가 1순위인 핵심 근거 1-2문장]
**관련 증거:**
• [직접 관련 Q&A 1]: [질문 요약] → [답변 핵심 내용] (점수: X점)
• [직접 관련 Q&A 2]: [질문 요약] → [답변 핵심 내용] (점수: X점)

**2순위: [회사명]**
**선정 이유:** [1순위 대비 어떤 점에서 아쉬운지, 어떤 점에서 좋은지]
**관련 증거:**
• [직접 관련 Q&A 1]: [질문 요약] → [답변 핵심 내용] (점수: X점)
• [직접 관련 Q&A 2]: [질문 요약] → [답변 핵심 내용] (점수: X점)

**[순위 결정 근거]**
- **1순위 > 2순위인 이유:** [구체적인 차이점과 근거]
- **고려되지 않은 회사들:** [다른 회사들이 추천에서 제외된 이유]

**[추천 신뢰도]**
- 관련 증거 품질: [상/중/하] - 얼마나 구체적이고 직접적인가
- 추천 확신도: [상/중/하] - 요구사항 대비 부합도

---

**추천 불가능한 경우:**

**[요구사항 분석]**
핵심 요구사항: [사용자가 찾는 것]
문제점: [왜 추천이 어려운지]

**[결과: 추천 불가]**
현재 평가 데이터에서는 요구사항에 **직접 부합하는** 충분한 증거를 찾을 수 없습니다.

**부족한 증거:**
- [요구사항1]: [어떤 종류의 증거가 필요한데 없는지]
- [요구사항2]: [어떤 종류의 증거가 필요한데 없는지]

**권장사항:**
1. 더 일반적인 요구사항으로 질문 수정
2. 해당 전문 분야 추가 평가 실시
3. 요구사항을 세분화하여 단계별 접근

=== 핵심 원칙 ===

**DO (반드시 할 것):**
- 질문과 **직접 관련된** 평가 항목만 근거로 사용
- 각 추천의 **구체적 근거**와 **순위 이유** 명시
- 평가 점수와 답변 내용을 **모두** 고려하여 판단
- 추천 못할 경우 **솔직하게** 인정하고 이유 설명

**DON'T (절대 하지 말 것):**
- 질문과 무관한 일반적 역량을 근거로 추천
- 추상적 표현이나 약한 증거로 강한 추천
- 억지로 순위를 채우기 위한 무리한 해석
- 회사의 전반적 분석보다는 **질문 특화** 추천에 집중"""

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2000,  # Increased for comprehensive reasoning
            temperature=0.1,   # Very low for consistent, analytical reasoning
            system="당신은 클라우드 및 MSP 선정 분야의 최고 수준 컨설턴트입니다. 데이터 기반의 논리적 분석과 실무적 통찰력을 겸비하여, 고객이 최적의 의사결정을 할 수 있도록 구조화되고 설득력 있는 추천을 제공합니다. 추천의 투명성을 위해 분석 과정과 논리적 근거를 명확히 제시하며, 추상적 표현보다는 구체적 근거와 실질적 가치에 집중합니다.",
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
            "model_used": "claude-3-haiku-enhanced-reasoning",
            "analysis_quality": "comprehensive_analytical_with_reasoning",
            "companies_analyzed": len(grouped_chunks),
            "total_evidence_points": sum(len(qa_list) for qa_list in grouped_chunks.values()),
            "analytics_summary": {company: analytics['overall_avg'] for company, analytics in company_analytics.items()},
            "reasoning_components": {
                "requirement_breakdown": True,
                "evidence_verification": True,
                "ranking_logic": True,
                "confidence_assessment": True,
                "excluded_companies_rationale": True
            }
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
    """
    Enhanced information summary leveraging Claude's analytical depth
    """
    import traceback
    import anthropic
    import os
    from collections import defaultdict
    
    query = question
    msp_name = extract_msp_name(question)

    all_results = collection.get(include=["metadatas"])
    all_msp_names = [meta.get("msp_name", "") for meta in all_results["metadatas"] if meta.get("msp_name")]

    matches = get_close_matches(msp_name, all_msp_names, n=1, cutoff=0.6)
    if not matches:
        return {"answer": "질문하신 회사명을 인식하지 못했습니다. 다시 시도해 주세요.", "advanced": False}
    best_match = matches[0]

    try:
        # Enhanced data collection - get comprehensive company profile
        query_vector = query_embed(question)
        query_results = collection.query(
            query_embeddings=[query_vector],
            n_results=15  # Increased for more comprehensive analysis
        )
        
        # Get ALL data for this company for complete profile
        all_company_data = collection.get(
            where={"msp_name": best_match},
            include=["metadatas"]
        )
        
        # Organize data by category and relevance
        relevant_chunks = []
        all_company_chunks = []
        category_data = defaultdict(list)
        
        # Process query-relevant data
        for chunk in query_results["metadatas"][0]:
            if chunk.get("msp_name") == best_match and chunk.get("answer") and chunk.get("question"):
                relevant_chunks.append({
                    "question": chunk['question'],
                    "answer": chunk['answer'],
                    "score": chunk.get('score', 0),
                    "category": chunk.get('category', '미분류'),
                    "group": chunk.get('group', '기타'),
                    "relevance": "high"  # Query-matched
                })
        
        # Process all company data for comprehensive profile
        for chunk in all_company_data["metadatas"]:
            if chunk.get("answer") and chunk.get("question"):
                category = chunk.get('category', '미분류')
                qa_item = {
                    "question": chunk['question'],
                    "answer": chunk['answer'],
                    "score": chunk.get('score', 0),
                    "group": chunk.get('group', '기타')
                }
                category_data[category].append(qa_item)
                
                # Add to all_company_chunks if not already in relevant_chunks
                if not any(existing['question'] == chunk['question'] for existing in relevant_chunks):
                    all_company_chunks.append({
                        "question": chunk['question'],
                        "answer": chunk['answer'],
                        "score": chunk.get('score', 0),
                        "category": chunk.get('category', '미분류'),
                        "group": chunk.get('group', '기타'),
                        "relevance": "supplementary"
                    })

        if not relevant_chunks and not all_company_chunks:
            return {"answer": "관련된 정보를 찾을 수 없습니다.", "advanced": False}

        # Calculate comprehensive analytics
        all_scores = [item['score'] for item in relevant_chunks + all_company_chunks if item['score']]
        category_analytics = {}
        
        for category, items in category_data.items():
            if items:
                scores = [item['score'] for item in items if item['score']]
                category_analytics[category] = {
                    'avg_score': round(sum(scores) / len(scores), 2) if scores else 0,
                    'count': len(items),
                    'excellence_areas': [item for item in items if item['score'] >= 4],
                    'improvement_areas': [item for item in items if item['score'] <= 2]
                }

        overall_avg = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0
        
        # Create rich context for Claude's analysis
        # 1. Query-relevant information (prioritized)
        relevant_context = []
        for chunk in relevant_chunks[:8]:  # Top 8 most relevant
            relevant_context.append(
                f"[관련도: 높음] Q: {chunk['question']}\n"
                f"A: {chunk['answer']}\n"
                f"평가: {chunk['score']}/5점 | 분야: {chunk['category']}"
            )
        
        # 2. Supplementary company information by category
        category_context = []
        for category, analytics in category_analytics.items():
            if analytics['count'] > 0:
                # Select best examples from each category
                top_items = sorted(category_data[category], key=lambda x: x['score'], reverse=True)[:3]
                
                category_block = f"\n=== {category} (평균: {analytics['avg_score']}/5점, {analytics['count']}개 항목) ===\n"
                for item in top_items:
                    category_block += f"• Q: {item['question'][:80]}{'...' if len(item['question']) > 80 else ''}\n"
                    category_block += f"  A: {item['answer'][:150]}{'...' if len(item['answer']) > 150 else ''} ({item['score']}/5점)\n\n"
                
                category_context.append(category_block)

        # 3. Company strength/weakness analysis
        strengths = []
        improvements = []
        for category, analytics in category_analytics.items():
            if analytics['avg_score'] >= 4.0:
                strengths.append(f"{category} ({analytics['avg_score']}/5점)")
            elif analytics['avg_score'] <= 3.0:
                improvements.append(f"{category} ({analytics['avg_score']}/5점)")

        # Create sophisticated prompt for Claude
        prompt = f"""당신은 클라우드 및 MSP 분야의 시니어 애널리스트입니다. {best_match}에 대한 종합적인 평가 데이터를 분석하여 사용자 질문에 전문적이고 통찰력 있는 답변을 제공해주세요.

사용자 질문: "{question}"

=== 회사 개요: {best_match} ===
전체 평가 평균: {overall_avg}/5점
평가 카테고리 수: {len(category_analytics)}개
총 평가 항목: {len(all_scores)}개

주요 강점 분야: {', '.join(strengths) if strengths else '특이사항 없음'}
개선 필요 분야: {', '.join(improvements) if improvements else '특이사항 없음'}

=== 질문 관련성 높은 정보 ===
{chr(10).join(relevant_context)}

=== 카테고리별 상세 역량 ===
{''.join(category_context)}

=== 전문가 분석 지침 ===

1. **정보 통합 및 맥락화**
   - 사용자 질문에 직접 답하되, 회사의 전반적 맥락에서 해석
   - 단편적 정보가 아닌 종합적 관점에서 분석
   - 평가 점수와 구체적 답변 내용을 균형있게 활용

2. **깊이 있는 통찰 제공**
   - 표면적 정보를 넘어 의미와 시사점 분석
   - 강점과 약점의 원인과 배경 파악
   - 경쟁사 대비 위치나 시장에서의 차별화 요소 식별

3. **실무적 관점 적용**
   - 잠재 고객이나 파트너 관점에서 유의미한 정보 우선 정리
   - 비즈니스 임팩트나 협업 시 고려사항 포함
   - 구체적 수치, 사례, 프로젝트명 등 검증 가능한 정보 강조

4. **균형잡힌 평가**
   - 긍정적 측면과 제한사항을 모두 고려
   - 과대포장 없이 사실에 기반한 객관적 서술
   - 불확실하거나 부족한 정보는 솔직하게 언급

5. **구조화된 정보 제공**
   - 핵심 내용을 명확하고 논리적으로 구성
   - 중요도에 따른 정보 우선순위 적용
   - 실행 가능한 인사이트나 권장사항 포함

=== 응답 형식 ===

**핵심 답변**
[사용자 질문에 대한 직접적이고 구체적인 답변 - 2-3문장]

**상세 분석**
[관련 평가 데이터를 바탕으로 한 심화 분석 - 구체적 점수, 사례, 프로젝트 포함]

**회사 맥락**
[해당 답변이 회사 전체 역량과 포지셔닝에서 갖는 의미]

**실무적 시사점**
[파트너십이나 프로젝트 관점에서의 고려사항 및 기대효과]

**종합 평가**
[객관적 강점과 제한사항을 포함한 균형잡힌 종합 의견]

=== 주의사항 ===
- 평가 데이터에 없는 정보는 추론하거나 일반화하지 마세요
- 구체적 근거 없는 마케팅성 표현은 피하세요
- 점수가 낮은 영역도 맥락을 고려하여 해석하세요
- 불충분한 정보 영역은 솔직하게 언급하세요"""

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,  # Increased for comprehensive analysis
            temperature=0.2,  # Lower for more analytical responses
            system="당신은 클라우드 및 MSP 산업의 시니어 애널리스트로서, 15년간의 시장 분석과 기업 평가 경험을 보유하고 있습니다. 데이터 기반의 객관적 분석과 실무적 통찰력을 결합하여, 고객이 정확한 의사결정을 할 수 있도록 균형잡히고 실행 가능한 정보를 제공합니다.",
            messages=[{
                "role": "user", 
                "content": prompt
            }]
        )
        
        answer = response.content[0].text.strip()
        
        # Enhanced post-processing
        answer = answer.replace("설루션", "솔루션")
        answer = answer.replace("클라우드 서비스", "클라우드 솔루션")
        
        return {
            "answer": answer, 
            "advanced": False, 
            "evidence": relevant_chunks,
            "model_used": "claude-3-haiku-enhanced-analyst",
            "company_analytics": {
                "overall_average": overall_avg,
                "total_evaluations": len(all_scores),
                "category_performance": category_analytics,
                "strengths": strengths,
                "improvement_areas": improvements
            },
            "data_coverage": {
                "query_relevant_items": len(relevant_chunks),
                "total_company_items": len(all_company_chunks) + len(relevant_chunks),
                "categories_covered": len(category_analytics)
            }
        }
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Claude API error: {str(e)}")

def run_msp_information_summary_pplx(question: str):
    """
    Enhanced Perplexity-based information summary with comprehensive web intelligence
    """
    import traceback
    import requests
    import os
    from collections import defaultdict
    
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
        # Enhanced internal data collection
        query_vector = query_embed(question)
        query_results = collection.query(
            query_embeddings=[query_vector],
            n_results=12  # Increased for comprehensive internal context
        )
        
        # Get comprehensive company profile from internal data
        all_company_data = collection.get(
            where={"msp_name": best_match},
            include=["metadatas"]
        )
        
        # Organize internal data
        internal_chunks = []
        category_data = defaultdict(list)
        
        # Process query-relevant internal data
        for chunk in query_results["metadatas"][0]:
            if chunk.get("msp_name") == best_match and chunk.get("answer") and chunk.get("question"):
                internal_chunks.append({
                    "question": chunk['question'],
                    "answer": chunk['answer'],
                    "score": chunk.get('score', 0),
                    "category": chunk.get('category', '미분류')
                })
        
        # Process all company data for context
        for chunk in all_company_data["metadatas"]:
            if chunk.get("answer") and chunk.get("question"):
                category = chunk.get('category', '미분류')
                category_data[category].append({
                    "question": chunk['question'],
                    "answer": chunk['answer'],
                    "score": chunk.get('score', 0)
                })

        # Calculate internal analytics
        all_internal_scores = []
        for category_items in category_data.values():
            all_internal_scores.extend([item['score'] for item in category_items if item['score']])
        
        internal_avg = round(sum(all_internal_scores) / len(all_internal_scores), 2) if all_internal_scores else 0
        
        # Create comprehensive internal context
        internal_context_blocks = []
        for chunk in internal_chunks[:6]:  # Top 6 most relevant
            internal_context_blocks.append(
                f"평가: {chunk['score']}/5점 | {chunk['category']}\n"
                f"Q: {chunk['question']}\n"
                f"A: {chunk['answer'][:200]}{'...' if len(chunk['answer']) > 200 else ''}"
            )
        
        internal_context = "\n\n".join(internal_context_blocks) if internal_context_blocks else "내부 평가 데이터 없음"
        
        # Adaptive prompt based on question complexity
        def detect_question_complexity(question: str):
            """Detect if question needs simple or complex analysis"""
            question_lower = question.lower()
            
            # Complex analysis indicators
            complex_indicators = [
                # Comparative terms
                "대비", "비교", "vs", "versus", "강점", "약점", "차이", "우위", "경쟁",
                # Alternative requests  
                "더 좋은", "대안", "옵션", "선택지", "추천", "어떤 회사",
                # Multiple requirements
                "그리고", "또한", "동시에", "함께",
                # Evaluation requests
                "평가", "분석", "검토", "판단"
            ]
            
            # Technical requirement indicators
            technical_indicators = [
                "멀티에이전트", "multi-agent", "rag", "text2sql", "mlops", 
                "챗봇", "chatbot", "파이프라인", "모니터링", "아키텍처"
            ]
            
            # Government/scale indicators  
            scale_indicators = [
                "정부", "공공", "대규모", "멀티사이트", "10곳", "여러", "다수"
            ]
            
            has_complex = any(indicator in question_lower for indicator in complex_indicators)
            has_technical = any(indicator in question_lower for indicator in technical_indicators) 
            has_scale = any(indicator in question_lower for indicator in scale_indicators)
            
            # Multiple conditions or specific complexity indicators = complex analysis
            complexity_score = sum([has_complex, has_technical, has_scale])
            
            if complexity_score >= 2 or has_complex:
                return "complex"
            elif has_technical or has_scale:
                return "moderate" 
            else:
                return "simple"
        
        complexity = detect_question_complexity(question)
        print(f"🧠 Question complexity detected: {complexity}")
        
        if complexity == "simple":
            # Simple, focused response for straightforward questions
            prompt = f"""당신은 MSP 전문가입니다. '{best_match}'에 대한 질문 "{question}"에 간결하고 정확하게 답변해주세요.

=== 내부 평가 정보 ===
회사: {best_match} (평가 평균: {internal_avg}/5점)
관련 평가 내용:
{internal_context}

=== 응답 지침 ===
- 질문에 직접 답하는 것에 집중하세요
- 내부 평가 데이터를 주요 근거로 활용하세요
- 최신 웹 정보로 보완하되, 과도하게 복잡하게 만들지 마세요
- 불필요한 비교나 분석은 피하고 핵심만 전달하세요
- 2-3개 문단으로 간결하게 정리하세요

웹에서 최신 정보를 확인하여 답변을 보완해주세요."""

        elif complexity == "moderate":
            # Moderate depth for technical or specific questions
            prompt = f"""당신은 MSP 기술 전문가입니다. '{best_match}'에 대한 질문 "{question}"에 전문적으로 답변해주세요.

=== 내부 평가 정보 ===
회사: {best_match} (평가 평균: {internal_avg}/5점)
관련 평가 내용:
{internal_context}

=== 분석 포인트 ===
- 질문에서 언급된 기술이나 요구사항에 대한 구체적 역량 평가
- 해당 분야에서의 실제 프로젝트 경험과 사례
- 기술적 강점과 제약사항의 균형잡힌 평가
- 실무적 관점에서의 적합성과 고려사항

=== 응답 구조 ===
**핵심 답변**: [질문에 대한 명확한 결론]
**역량 분석**: [구체적 기술 역량과 경험]  
**실무 고려사항**: [협업 시 유의점이나 권장사항]

웹에서 관련 기술 동향과 프로젝트 사례를 조사하여 포함해주세요."""

        else:  # complex
            # Full comprehensive analysis for complex questions
            prompt = f"""당신은 클라우드 및 MSP 산업의 시니어 리서치 애널리스트입니다. '{best_match}'에 대한 복합 질문 "{question}"에 답변하기 위해, 내부 평가 데이터와 최신 웹 정보를 종합하여 전문적인 분석을 제공해주세요.

=== 내부 평가 데이터 (기준점) ===
회사명: {best_match}
내부 평가 평균: {internal_avg}/5점 (총 {len(all_internal_scores)}개 평가 항목)
평가 카테고리: {len(category_data)}개 분야

주요 내부 평가 내용:
{internal_context}

=== 종합 분석 지침 ===

1. **질문 유형별 필수 요소**
   - 비교/경쟁 질문 ("대비", "강점", "약점", "vs") → 반드시 경쟁사 분석과 순위 비교 포함
   - 기술 역량 질문 (구체적 기술명 언급) → 해당 기술의 직접 경험과 프로젝트 사례 검증
   - 대안 요청 ("더 좋은", "옵션", "추천") → 구체적 대안 회사들과 선택 기준 제시
   - 정부/공공 언급 → 공공 프로젝트 경험과 정부 규정 준수 능력 평가

2. **증거 기반 분석 원칙**
   - 구체적 기술명이 언급되면 해당 기술의 실제 구현 경험만 인정
   - 일반적 AI 역량을 특수 기술 전문성으로 확대 해석 금지
   - 점수만으로 판단하지 말고 답변 내용의 구체성과 관련성 우선 평가
   - 경쟁사 비교 시 동일한 기준으로 다른 회사들의 역량도 검토

=== 응답 필수 구성 요소 ===

**💡 직접 답변**
[사용자 질문에 대한 명확하고 구체적인 답변 - "예/아니오" 또는 "적합/부적합" 등 명확한 결론 포함]

**🔍 상세 분석**
- **{best_match} 역량 평가**: [해당 분야 구체적 경험과 프로젝트 사례, 점수 근거]
- **기술적 적합성**: [언급된 기술들에 대한 개별 역량 평가]
- **최신 동향**: [웹에서 확인된 최근 프로젝트나 기술 발전 사항]

**⚖️ 경쟁 비교 (비교 질문인 경우 필수)**
- **직접 경쟁사**: [유사한 기술 역량을 가진 다른 MSP들과의 비교]
- **우위 요소**: [{best_match}가 경쟁사 대비 앞서는 구체적 부분]
- **열위 요소**: [경쟁사가 더 나은 구체적 부분]
- **대안 추천**: [더 적합한 회사가 있다면 구체적 이유와 함께 제시]

**🎯 실무 권장사항**
- **선택 기준**: [해당 프로젝트에서 {best_match}를 선택해야 하는 구체적 조건]
- **주의사항**: [협업 시 반드시 확인해야 할 제약 요소나 리스크]
- **성공 요인**: [프로젝트 성공을 위해 필요한 추가 조건이나 지원]

=== 품질 체크리스트 ===
✅ 질문에서 요구한 모든 요소에 대해 구체적으로 답변했는가?
✅ 비교 요청 시 실제 경쟁사와 비교 분석을 제공했는가?
✅ 기술 역량 평가 시 해당 기술의 직접 경험을 확인했는가?
✅ 대안 요청 시 더 나은 선택지를 구체적으로 제시했는가?
✅ 일반론이 아닌 구체적 근거와 사례를 바탕으로 결론을 도출했는가?

위 지침에 따라 종합적이고 전문적인 분석을 제공해주세요."""

    except Exception as e:
        traceback.print_exc()
        return {"answer": f"내부 데이터 처리 중 오류가 발생했습니다: {str(e)}", "advanced": True}

    # Enhanced Perplexity API call
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
                    {
                        "role": "system", 
                        "content": "당신은 15년 경력의 클라우드 및 MSP 산업 전문 리서치 애널리스트입니다. 내부 평가 데이터와 최신 웹 정보를 종합하여 정확하고 실용적인 비즈니스 인텔리전스를 제공하며, 팩트에 기반한 객관적 분석과 실행 가능한 인사이트를 중시합니다."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.2,  # Lower for more factual analysis
                "max_tokens": 1500,  # Increased for comprehensive analysis
                "top_p": 0.8
            },
            timeout=45  # Increased timeout for comprehensive web search
        )
        
        print(f"🔎 Perplexity API status: {response.status_code}")
        
        if response.status_code == 200:
            import re
            result = response.json()
            answer = result["choices"][0]["message"]["content"].strip()
            
            # Enhanced post-processing for professional consistency
            # Remove citation markers that might interfere with readability
            answer = re.sub(r"\[\d+\]", "", answer)
            
            # Fix common terminology
            professional_fixes = {
                "설루션": "솔루션",
                "클라우드 서비스": "클라우드 솔루션",
                "빅데이터": "빅데이터",
                "머신러닝": "머신러닝",
                "딥러닝": "딥러닝",
                "인공지능": "AI"
            }
            
            for old_term, new_term in professional_fixes.items():
                answer = answer.replace(old_term, new_term)
            
            # Clean up formatting
            answer = re.sub(r"\n{3,}", "\n\n", answer)  # Remove excessive line breaks
            answer = answer.strip()
            
            return {
                "answer": answer, 
                "advanced": True, 
                "evidence": internal_chunks,
                "model_used": "perplexity-sonar-enhanced",
                "data_integration": {
                    "internal_data_points": len(internal_chunks),
                    "internal_average": internal_avg,
                    "categories_covered": len(category_data),
                    "web_enhanced": True
                },
                "analysis_type": "comprehensive_web_intelligence"
            }
        else:
            # Fallback to internal data analysis if Perplexity fails
            print(f"❌ Perplexity API failed: {response.status_code}, falling back to internal analysis")
            
            if internal_chunks:
                fallback_answer = f"""**[내부 데이터 기반 분석]**

**핵심 답변**
{best_match}에 대한 질문 "{question}"에 대해 내부 평가 데이터를 바탕으로 분석한 결과입니다.

**평가 현황**
- 내부 평가 평균: {internal_avg}/5점
- 평가 항목 수: {len(all_internal_scores)}개
- 평가 카테고리: {len(category_data)}개 분야

**주요 평가 내용**
{chr(10).join([f"• [{chunk['category']}] {chunk['question'][:60]}{'...' if len(chunk['question']) > 60 else ''} (점수: {chunk['score']}/5)" for chunk in internal_chunks[:5]])}

**제한사항**
외부 웹 정보 연동에 실패하여 내부 평가 데이터만을 기반으로 한 제한적 분석입니다. 최신 정보나 시장 동향은 별도 확인이 필요합니다."""
                
                return {
                    "answer": fallback_answer,
                    "advanced": True,
                    "evidence": internal_chunks,
                    "model_used": "internal-fallback",
                    "data_integration": {
                        "internal_data_points": len(internal_chunks),
                        "internal_average": internal_avg,
                        "web_enhanced": False,
                        "fallback_reason": "perplexity_api_failure"
                    }
                }
            else:
                return {
                    "answer": f"{best_match}에 대한 충분한 정보를 찾을 수 없습니다.", 
                    "advanced": True
                }
                
    except Exception as e:
        traceback.print_exc()
        return {
            "answer": f"웹 기반 분석 중 오류가 발생했습니다: {str(e)}", 
            "advanced": True
        }

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
            max_tokens=1500,
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

import subprocess
import json
import traceback
import anthropic
import os

def call_naver_search_server(command: str, *args):
    """네이버 검색 서버 호출"""
    try:
        cmd = ["python3", "./mcp/naver_search_server.py", command] + list(args)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=45,  # 기존과 동일한 타임아웃
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"서버 호출 실패 (코드: {result.returncode}): {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return "네이버 검색 서버 타임아웃 (45초 초과)"
    except Exception as e:
        return f"서버 호출 중 오류: {str(e)}"

def parse_search_results_for_claude(raw_text: str, search_type: str = "news"):
    """
    검색 결과를 Claude가 분석하기 좋은 형태로 변환
    """
    items = []
    
    if not raw_text or "오류" in raw_text or "실패" in raw_text:
        return items
    
    try:
        if search_type == "news":
            sections = raw_text.split("📰 뉴스")[1:]
        else:
            sections = raw_text.split("🌐 웹문서")[1:]
        
        for section in sections:
            lines = section.strip().split('\n')
            item = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith('제목:'):
                    item['title'] = line.replace('제목:', '').strip()
                elif line.startswith('세부내용:') or line.startswith('요약:'):
                    item['description'] = line.replace('세부내용:', '').replace('요약:', '').strip()
                elif line.startswith('날짜:'):
                    item['pubDate'] = line.replace('날짜:', '').strip()
                elif line.startswith('링크:'):
                    item['link'] = line.replace('링크:', '').strip()
            
            if item.get('title') and item.get('description'):
                items.append(item)
        
        return items
        
    except Exception as e:
        print(f"파싱 오류: {e}")
        return []

def run_msp_news_summary_mcp(question: str):
    """
    MCP 아키텍처 기반 뉴스 요약
    """
    
    msp_name = extract_msp_name(question)
    if not msp_name:
        return {"answer": "회사명을 인식하지 못했습니다. 다시 시도해 주세요.", "advanced": True}

    # 내부 벡터 DB 검색
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
        print(f"MCP 서버를 통한 '{msp_name}' 검색 시작...")
        
        # MCP 서버를 통한 검색 (기존 API 호출 대체)
        news_raw = call_naver_search_server("news", msp_name, "15")
        web_raw = call_naver_search_server("web", msp_name, "7")
        
        print(f"MCP 검색 완료")
        
        # 검색 결과를 기존 형식으로 변환
        news_items_parsed = parse_search_results_for_claude(news_raw, "news")
        web_items_parsed = parse_search_results_for_claude(web_raw, "web")
        
        if not news_items_parsed:
            return {"answer": f"{msp_name}에 대한 뉴스 기사를 찾을 수 없습니다.", "advanced": True}

        # 데이터 정리 로직
        def clean_text(text):
            return text.replace('<b>', '').replace('</b>', '').replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

        # 포맷팅
        news_items = []
        for i, item in enumerate(news_items_parsed[:12], 1):
            title = clean_text(item.get('title', ''))
            desc = clean_text(item.get('description', ''))
            pub_date = item.get('pubDate', 'N/A')
            
            if title and desc:
                news_items.append(f"{i}. [{pub_date}] {title}\n   세부내용: {desc}")

        web_items = []
        for i, item in enumerate(web_items_parsed[:5], 1):
            title = clean_text(item.get('title', ''))
            desc = clean_text(item.get('description', ''))
            
            if title and desc and len(desc) > 50:
                web_items.append(f"{i}. {title}\n   요약: {desc}")

        article_text = "\n\n".join(news_items)
        web_text = "\n\n".join(web_items)

        # Claude 프롬프트
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
        return {"answer": f"MCP 기반 검색에 실패했습니다: {str(e)}", "advanced": True}

    # Claude API 호출
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            temperature=0.2,
            system="당신은 10년 이상 경력의 클라우드 및 MSP 전문 컨설턴트입니다. 다양한 정보원을 종합 분석하여 객관적이고 실용적인 통찰을 제공하며, 구체적 근거와 데이터에 기반한 전문가 수준의 평가를 중시합니다.",
            messages=[{
                "role": "user", 
                "content": prompt
            }]
        )
        
        answer = response.content[0].text.strip()
        answer = answer.replace("설루션", "솔루션")
        answer = answer.replace("클라우드 서비스", "클라우드 솔루션")
        
        return {
            "answer": answer, 
            "advanced": True, 
            "evidence": news_items_parsed[:12], 
            "web_evidence": web_items_parsed[:5],
            "model_used": "mcp-naver-server + claude-3-haiku-enhanced",
            "data_summary": {
                "news_articles": len(news_items),
                "web_documents": len(web_items),
                "internal_qa_pairs": len(db_chunks),
                "total_sources": len(news_items) + len(web_items) + len(db_chunks)
            },
            "mcp_integration": {
                "server_type": "simple_subprocess",
                "data_source": "naver_search_server",
                "architecture": "modular_mcp_approach"
            }
        }
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Claude API error: {str(e)}")

# 헬스체크 함수
def check_mcp_server_status():
    """MCP 서버 상태 확인"""
    try:
        result = call_naver_search_server("extract", "테스트 질문")
        return "MCP 서버 정상 작동" if "테스트" in result else f"MCP 서버 이상: {result[:100]}"
    except Exception as e:
        return f"MCP 서버 연결 실패: {str(e)}"
