from msp_core import query_embed, collection  # Reuse existing infrastructure
from fastapi import HTTPException
import anthropic
import os
from openai import OpenAI
from collections import defaultdict
import traceback

def run_multi_llm_msp_recommendation(question: str, min_score: int):
    """
    Enhanced MSP recommendation using multi-LLM interaction cycle:
    HCX Responder → Claude Critic → Claude Refiner
    """
    try:
        # Step 1: Collect and prepare data
        raw_data = collect_vector_data(question, min_score)
        if not raw_data["grouped_chunks"]:
            return {"answer": "해당 조건에 맞는 평가 데이터를 찾을 수 없습니다."}
        
        # Step 2: Manage context and select companies
        context_data = manage_context_selection(raw_data["grouped_chunks"], question)
        
        # Step 3: HCX Responder (with fallback)
        hcx_result = call_hcx_responder(question, context_data["full_context"])
        
        # Step 4: Claude Critic
        critic_result = call_claude_critic(question, hcx_result["recommendation"], context_data["full_context"])
        
        # Step 5: Claude Refiner
        final_result = call_claude_refiner(question, hcx_result["recommendation"], 
                                         critic_result["analysis"], context_data["full_context"])
        
        # Step 6: Compile final response
        return compile_final_response(
            final_result["recommendation"],
            raw_data,
            context_data,
            hcx_result,
            critic_result,
            final_result
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Multi-LLM recommendation failed: {str(e)}")


def collect_vector_data(question: str, min_score: int):
    """Collect and organize data from vector database"""
    from collections import defaultdict
    
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

    # Calculate analytics for each company
    company_analytics = {}
    for msp, qa_list in grouped_chunks.items():
        scores = [qa['score'] for qa in qa_list]
        analytics = {
            'overall_avg': round(sum(scores) / len(scores), 2),
            'evidence_quality': len([qa for qa in qa_list if len(qa['answer']) > 150]),
            'total_responses': len(qa_list)
        }
        company_analytics[msp] = analytics

    return {
        "grouped_chunks": grouped_chunks,
        "company_analytics": company_analytics,
        "query_results": query_results
    }


def manage_context_selection(grouped_chunks: dict, question: str):
    """Manage context length by selecting top companies and formatting context"""
    
    # Determine context limit based on question complexity
    question_complexity_indicators = len([
        keyword for keyword in ['대비', '비교', 'vs', '강점', '약점', '차이', '우위', '경쟁', 
                               '더 좋은', '대안', '옵션', '선택지', '추천', 'ai', '머신러닝', 
                               '정부', '공공', '대규모', '멀티']
        if keyword in question.lower()
    ])
    
    if question_complexity_indicators >= 3:
        max_companies = 7
    elif question_complexity_indicators >= 1:
        max_companies = 5
    else:
        max_companies = 4
    
    print(f"🧠 Question complexity indicators: {question_complexity_indicators}, limiting to top {max_companies} companies")
    
    # Sort and select companies
    company_analytics = {msp: calculate_company_analytics(qa_list) for msp, qa_list in grouped_chunks.items()}
    company_list = [(msp, qa_list, company_analytics[msp]) for msp, qa_list in grouped_chunks.items()]
    company_list.sort(key=lambda x: x[2]['overall_avg'], reverse=True)
    selected_companies = company_list[:max_companies]
    
    # Format context
    full_context = format_company_context(selected_companies)
    
    # Track exclusions
    excluded_companies = [item[0] for item in company_list[max_companies:]]
    if excluded_companies:
        print(f"📊 Context management: Selected top {max_companies} companies by avg score, excluded: {excluded_companies}")
    
    return {
        "full_context": full_context,
        "selected_companies": selected_companies,
        "excluded_companies": excluded_companies,
        "max_companies": max_companies,
        "context_stats": {
            "total_companies_available": len(grouped_chunks),
            "companies_included": len(selected_companies),
            "companies_excluded": excluded_companies,
            "context_length_chars": len(full_context),
            "selection_criteria": "overall_avg_score_descending"
        }
    }


def calculate_company_analytics(qa_list: list):
    """Calculate analytics for a single company"""
    scores = [qa['score'] for qa in qa_list]
    return {
        'overall_avg': round(sum(scores) / len(scores), 2),
        'evidence_quality': len([qa for qa in qa_list if len(qa['answer']) > 150]),
        'total_responses': len(qa_list)
    }


def format_company_context(selected_companies: list):
    """Format company data into context string for LLMs"""
    analysis_context = []
    
    for msp, qa_list, analytics in selected_companies:
        sorted_qa = sorted(qa_list, key=lambda x: (x['score'], len(x['answer'])), reverse=True)
        top_evidence = sorted_qa[:6]
        
        company_block = f"""
=== {msp} 분석 ===
평균: {analytics['overall_avg']}/5점 | 응답 수: {analytics['total_responses']}개
상세 답변: {analytics['evidence_quality']}개

핵심 근거:
{chr(10).join([f"[{qa['score']}점] {qa['category']} | Q: {qa['question'][:60]}{'...' if len(qa['question']) > 60 else ''}" + 
              f"{chr(10)}    A: {qa['answer'][:200]}{'...' if len(qa['answer']) > 200 else ''}"
              for qa in top_evidence])}
"""
        analysis_context.append(company_block)
    
    return "\n".join(analysis_context)


def call_hcx_responder(question: str, full_context: str):
    """Call HCX for initial recommendation with quality validation and fallback"""
    import os
    from openai import OpenAI
    
    hcx_prompt = f"""당신은 MSP 전문가입니다. 다음 평가 데이터를 분석하여 사용자 요구사항에 맞는 회사를 추천해주세요.

사용자 요구사항: "{question}"

{full_context}

=== 분석 지침 ===
1. 사용자 질문과 직접 관련된 역량을 가진 회사들을 식별
2. 각 회사의 해당 분야 경험과 평가 점수를 종합 분석
3. 상위 2-3개 회사를 선정하고 순위 결정
4. 각 추천의 구체적 근거 제시

응답 형식:
**추천 순위**
1순위: [회사명] - [핵심 선정 이유]
2순위: [회사명] - [핵심 선정 이유]

**상세 근거**
각 회사별로 관련 평가 내용과 점수를 바탕으로 구체적 설명"""

    # Call HCX
    CLOVA_API_KEY = os.getenv("CLOVA_API_KEY_OPENAI")
    API_URL = "https://clovastudio.stream.ntruss.com/v1/openai"
    hcx_client = OpenAI(api_key=CLOVA_API_KEY, base_url=API_URL)
    
    hcx_response = hcx_client.chat.completions.create(
        model="HCX-005",
        messages=[
            {"role": "system", "content": "MSP 평가 전문가로서 데이터 기반의 객관적 추천을 제공합니다."},
            {"role": "user", "content": hcx_prompt}
        ],
        top_p=0.6,
        temperature=0.3,
        max_tokens=800
    )
    
    hcx_recommendation = hcx_response.choices[0].message.content.strip()
    print(f"✅ HCX Response length: {len(hcx_recommendation)} chars")
    
    # Validate and potentially use fallback
    validation_result = validate_and_fallback_hcx(hcx_recommendation, question, hcx_client, full_context)
    
    return {
        "recommendation": validation_result["final_recommendation"],
        "quality_metrics": validation_result["quality_metrics"],
        "fallback_used": validation_result["fallback_used"]
    }


def validate_and_fallback_hcx(hcx_recommendation: str, question: str, hcx_client, full_context: str):
    """Validate HCX response quality and apply fallback if needed"""
    
    def validate_hcx_response(response_text, question):
        """Validate HCX response quality"""
        validation_issues = []
        
        # Check 1: Minimum length
        if len(response_text) < 200:
            validation_issues.append("response_too_short")
        
        # Check 2: Contains ranking/priority indicators
        ranking_indicators = ['1순위', '2순위', '추천', '순위', '1위', '2위', '첫 번째', '두 번째']
        has_ranking = any(indicator in response_text for indicator in ranking_indicators)
        if not has_ranking:
            validation_issues.append("missing_ranking_structure")
        
        # Check 3: Contains specific evidence
        evidence_indicators = ['점', '프로젝트', '사례', '경험', '기술', '역량', '점수']
        mentioned_evidence = sum(1 for indicator in evidence_indicators if indicator in response_text)
        if mentioned_evidence < 3:
            validation_issues.append("insufficient_evidence_detail")
        
        # Check 4: Avoid generic/vague responses
        vague_phrases = ['전반적으로', '일반적으로', '대체로', '평균적으로', '보통', '그런대로']
        vague_count = sum(1 for phrase in vague_phrases if phrase in response_text)
        if vague_count > 2:
            validation_issues.append("too_vague")
        
        return validation_issues
    
    # Validate initial response
    validation_issues = validate_hcx_response(hcx_recommendation, question)
    fallback_used = False
    final_recommendation = hcx_recommendation
    
    if validation_issues:
        print(f"⚠️ HCX validation issues detected: {validation_issues}")
        
        # Attempt fallback
        fallback_result = attempt_hcx_fallback(question, full_context, hcx_client)
        
        if fallback_result["success"]:
            fallback_issues = validate_hcx_response(fallback_result["recommendation"], question)
            
            if len(fallback_issues) < len(validation_issues):
                print(f"✅ Fallback improved quality: {len(validation_issues)} → {len(fallback_issues)} issues")
                final_recommendation = fallback_result["recommendation"]
                validation_issues = fallback_issues
                fallback_used = True
            else:
                print(f"⚠️ Fallback didn't improve significantly, using original response")
        else:
            print(f"❌ Fallback failed: {fallback_result['error']}")
    else:
        print(f"✅ HCX response passed validation checks")
    
    return {
        "final_recommendation": final_recommendation,
        "quality_metrics": {
            "validation_issues": validation_issues,
            "response_length": len(final_recommendation),
            "quality_score": max(0, 10 - len(validation_issues))
        },
        "fallback_used": fallback_used
    }


def attempt_hcx_fallback(question: str, full_context: str, hcx_client):
    """Attempt fallback with enhanced prompt for HCX"""
    fallback_prompt = f"""이전 응답이 너무 간략하거나 구체성이 부족했습니다. 다음 평가 데이터를 바탕으로 더 상세하고 구체적인 MSP 추천을 해주세요.

사용자 요구사항: "{question}"

{full_context}

=== 강화된 분석 지침 ===
1. 반드시 구체적인 회사명과 명확한 순위를 제시할 것
2. 각 추천마다 평가 점수와 구체적 프로젝트/기술 경험을 언급할 것
3. 사용자 질문의 핵심 키워드를 반드시 포함하여 관련성을 명확히 할 것
4. 일반적/추상적 표현 대신 구체적 근거와 수치를 활용할 것

필수 응답 형식:
**1순위: [정확한 회사명]**
선정 이유: [구체적 기술/경험 + 평가점수 언급]
관련 증거: [구체적 Q&A 내용과 점수]

**2순위: [정확한 회사명]** 
선정 이유: [1순위와의 차이점 + 구체적 근거]
관련 증거: [구체적 Q&A 내용과 점수]

최소 400자 이상, 구체적 근거 중심으로 작성해주세요."""

    try:
        fallback_response = hcx_client.chat.completions.create(
            model="HCX-005",
            messages=[
                {"role": "system", "content": "MSP 평가 전문가로서 구체적이고 상세한 데이터 기반 추천을 제공합니다. 일반적 표현을 피하고 구체적 근거와 수치를 중심으로 응답합니다."},
                {"role": "user", "content": fallback_prompt}
            ],
            top_p=0.5,
            temperature=0.2,
            max_tokens=1000
        )
        
        return {
            "success": True,
            "recommendation": fallback_response.choices[0].message.content.strip()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def call_claude_critic(question: str, hcx_recommendation: str, full_context: str):
    """Call Claude to critically analyze HCX recommendation"""
    import anthropic
    import os
    
    critic_prompt = f"""당신은 MSP 평가의 품질 검증 전문가입니다. 다른 AI가 제공한 추천을 비판적으로 분석해주세요.

원본 사용자 질문: "{question}"

=== HCX 모델의 추천 결과 ===
{hcx_recommendation}

=== 원본 평가 데이터 ===
{full_context}

=== 비판적 분석 지침 ===
1. **관련성 검증**: 추천된 회사들이 사용자 요구사항과 직접 관련이 있는가?
2. **근거 품질**: 제시된 근거가 구체적이고 설득력 있는가?
3. **누락 분석**: 더 적합한 회사가 누락되었는가?
4. **순위 타당성**: 제시된 순위가 논리적으로 타당한가?
5. **편향 검증**: 특정 요소(점수, 회사 크기 등)에 과도하게 의존하지 않았는가?

=== 분석 결과 형식 ===
**검증 결과**
- 추천 적절성: [적절/부적절/부분적]
- 주요 강점: [HCX 추천의 좋은 점들]
- 발견된 문제: [논리적 오류, 누락, 편향 등]

**개선 제안**
- 추가 고려사항: [놓친 중요한 요소들]
- 대안 후보: [고려해야 할 다른 회사들]
- 순위 조정 필요성: [순위 변경이 필요한 이유]"""

    claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    critic_response = claude_client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1000,
        temperature=0.1,
        system="MSP 평가 품질 검증 전문가로서 다른 AI의 추천을 객관적으로 분석하고 개선점을 제시합니다.",
        messages=[{
            "role": "user", 
            "content": critic_prompt
        }]
    )
    
    critic_analysis = critic_response.content[0].text.strip()
    print(f"✅ Critic Analysis length: {len(critic_analysis)} chars")
    
    return {
        "analysis": critic_analysis,
        "analysis_length": len(critic_analysis)
    }


def call_claude_refiner(question: str, hcx_recommendation: str, critic_analysis: str, full_context: str):
    """Call Claude to create final refined recommendation"""
    import anthropic
    import os
    
    refiner_prompt = f"""당신은 MSP 선정 최종 의사결정 전문가입니다. 초기 추천과 비판적 분석을 종합하여 최종 추천을 제공해주세요.

사용자 질문: "{question}"

=== 초기 추천 (HCX) ===
{hcx_recommendation}

=== 비판적 분석 (Claude Critic) ===
{critic_analysis}

=== 원본 평가 데이터 ===
{full_context}

=== 최종 추천 지침 ===
1. 초기 추천의 장점을 유지하면서 비판적 분석의 개선점 반영
2. 사용자 요구사항과의 직접적 부합도를 최우선 고려
3. 모든 결론에 대해 구체적이고 검증 가능한 근거 제시
4. 선택하지 않은 회사들에 대한 명확한 제외 이유 설명

=== 최종 응답 형식 ===
**[요구사항 분석]**
핵심 요구사항: [사용자가 찾는 것]
중요 키워드: [기술/조건 키워드들]

**[최종 추천]**
**1순위: [회사명]**
**선정 이유:** [핵심 근거 1-2문장]
**관련 증거:**
• [직접 관련 Q&A 1]: [요약] (점수: X점)
• [직접 관련 Q&A 2]: [요약] (점수: X점)

**2순위: [회사명]**
**선정 이유:** [1순위 대비 차이점과 장점]
**관련 증거:**
• [직접 관련 Q&A]: [요약] (점수: X점)

**[최종 판단 근거]**
- **순위 결정 이유:** [구체적 차이점]
- **제외된 회사들:** [다른 회사 제외 이유]
- **추천 신뢰도:** [상/중/하] - [신뢰도 근거]"""

    claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    final_response = claude_client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1500,
        temperature=0.1,
        system="MSP 선정 최종 의사결정 전문가로서 모든 정보를 종합하여 최적의 추천을 제공합니다.",
        messages=[{
            "role": "user", 
            "content": refiner_prompt
        }]
    )
    
    final_recommendation = final_response.content[0].text.strip()
    print(f"✅ Final Recommendation length: {len(final_recommendation)} chars")
    
    # Post-processing
    final_recommendation = final_recommendation.replace("설루션", "솔루션")
    
    return {
        "recommendation": final_recommendation,
        "recommendation_length": len(final_recommendation)
    }


def compile_final_response(final_recommendation: str, raw_data: dict, context_data: dict, 
                          hcx_result: dict, critic_result: dict, final_result: dict):
    """Compile all results into final response format"""
    
    return {
        "answer": final_recommendation,
        "evidence": raw_data["query_results"]["metadatas"][0],
        "model_used": "multi-llm-hcx-claude-critic-refiner",
        "analysis_quality": "multi_model_validated",
        "companies_analyzed": len(raw_data["grouped_chunks"]),
        "context_management": context_data["context_stats"],
        "hcx_quality_metrics": hcx_result["quality_metrics"],
        "processing_steps": {
            "step1_hcx_responder": hcx_result["quality_metrics"]["response_length"],
            "step2_claude_critic": critic_result["analysis_length"], 
            "step3_claude_refiner": final_result["recommendation_length"]
        },
        "intermediate_outputs": {
            "hcx_initial": hcx_result["recommendation"],
            "claude_criticism": critic_result["analysis"]
        },
        "system_metadata": {
            "fallback_used": hcx_result["fallback_used"],
            "validation_passed": len(hcx_result["quality_metrics"]["validation_issues"]) == 0,
            "context_selection_method": "avg_score_based"
        }
    }
