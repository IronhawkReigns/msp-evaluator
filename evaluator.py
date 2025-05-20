import os
import time
import random
import pandas as pd
import requests
import re

# Load rubric from Excel
rubric_df = pd.read_excel("Criteria.xlsx")
rubric_lookup = {
    row["Key Questions"].strip(): row["Rubric"].strip()
    for _, row in rubric_df.iterrows()
    if pd.notna(row["Key Questions"]) and pd.notna(row["Rubric"])
}

def evaluate_answer(question, answer):
    CLOVA_API_KEY = os.getenv("CLOVA_API_KEY")
    REQUEST_ID = f"msp-evaluator-{random.randint(100000,999999)}"
    API_URL = "https://clovastudio.stream.ntruss.com/testapp/v2/tasks/bjlkpn9s/chat-completions"
    model = "ft:tuning-1883-250519-111923-2qjqh"

    rubric = rubric_lookup.get(question.strip(), "해당 질문에 대한 평가 기준이 명확하지 않습니다.")

    system_prompt = (
        "당신은 Naver Cloud에서 클라우드 MSP 파트너사를 평가하는 모델입니다. 응답이 명확하고 신뢰할 수 있는 평가 기준을 따르되, 실무적으로 충분하다고 판단되는 응답에 대해서는 긍정적으로, 후한 점수로 평가하십시오."
        f"점수는 다음을 기준으로 공정하고 일관되게 부여해야 합니다:\n\n"
        f"Rubric 기준:\n{rubric}\n\n"
        "각 질문에 대해 1~5점의 점수를 부여하나 반드시 숫자 하나로만 답변해 주십시오. (예: 4)"
    )

    user_prompt = f"[질문] {question}\n[응답] {answer}\n점수만 숫자로 알려주세요. (1~5 중 하나) 최종적으로 점수를 매기기 전에 왜 그렇게 매겼는지 상세히 재고하나 *반드시 설명을 제외한 숫자 하나만* 기록해 주세요."

    headers = {
        "Authorization": f"Bearer {CLOVA_API_KEY}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": REQUEST_ID,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    body = {
        "topP": 0.8,
        "topK": 0,
        "maxTokens": 10,
        "temperature": 0.7,
        "repeatPenalty": 5.0,
        "includeAiFilters": True,
        "stopBefore": [],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }

    response = requests.post(API_URL, json=body, headers=headers)
    result = response.json()
    if "result" in result:
        message = result["result"]["message"]["content"].strip()
        match = re.search(r"\b([1-5])\b", message)
        if match:
            return int(match.group(1))
        else:
            return f"Unexpected content: {message}"
    else:
        return f"Error in API response: {result}"


# --- Category summary functions ---
def compute_category_scores_from_dataframe(df):
    df['설명'] = df['설명'].replace('', pd.NA).ffill()
    df['Present Lv.'] = pd.to_numeric(df['Present Lv.'], errors='coerce')

    # Keep only rows with valid questions and scores
    valid_rows = df[df['Key Questions'].notna() & df['Present Lv.'].notna()].copy()

    category_scores = {}
    grouped = valid_rows.groupby('설명', sort=False)

    for category, group in grouped:
        question_count = len(group)
        total_score = group['Present Lv.'].sum()
        max_score = question_count * 5
        percentage = round(total_score / max_score, 4) if max_score > 0 else 0.0

        category_scores[category] = percentage

    return category_scores

def append_category_scores_to_sheet(sheet_df):
    sheet_df['설명'] = sheet_df['설명'].replace('', pd.NA).ffill()
    sheet_df['Present Lv.'] = pd.to_numeric(sheet_df['Present Lv.'], errors='coerce')
    valid_rows = sheet_df[sheet_df['Key Questions'].notna() & sheet_df['Present Lv.'].notna()].copy()
    allowed_categories = {
        "AI 전문 인력 구성",
        "프로젝트 경험 및 성공 사례",
        "지속적인 교육 및 학습",
        "프로젝트 관리 및 커뮤니케이션",
        "AI 윤리 및 책임 의식",
        "AI 기술 연구 능력",
        "AI 모델 개발 능력",
        "AI 플랫폼 및 인프라 구축 능력",
        "데이터 처리 및 분석 능력",
        "AI 기술의 융합 및 활용 능력",
        "AI 기술의 특허 및 인증 보유 현황",
        "다양성 및 전문성",
        "안정성",
        "확장성 및 유연성",
        "사용자 편의성",
        "보안성",
        "기술 지원 및 유지보수",
        "차별성 및 경쟁력",
        "개발 로드맵 및 향후 계획"
    }
    valid_rows = valid_rows[valid_rows['설명'].isin(allowed_categories)]

    grouped = valid_rows.groupby('설명', sort=False)

    category_scores = {}
    question_counts = {}

    for category, group in grouped:
        score_sum = group['Present Lv.'].sum()
        question_count = len(group)
        max_score = question_count * 5
        percentage = round(score_sum / max_score, 4) if max_score > 0 else 0.0
        category_scores[category] = percentage
        question_counts[category] = question_count

    total_score = valid_rows['Present Lv.'].sum()
    question_count = len(valid_rows)
    max_score = question_count * 5
    avg_score = round((total_score / max_score) * 100, 2) if max_score > 0 else 0.0

    section_headers = {"인적역량", "AI기술역량", "솔루션 역량"}
    summary_rows = [["총점", f"{avg_score:.2f}%", question_count]]
    for category, score in category_scores.items():
        if category in section_headers:
            continue
        summary_rows.append([category, f"{score * 100:.2f}%", question_counts[category]])

    summary_df = pd.DataFrame(summary_rows, columns=["Category", "Score (%)", "Questions"])
    return summary_df
