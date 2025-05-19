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
