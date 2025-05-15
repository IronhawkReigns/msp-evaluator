import os
import time
import random
import pandas as pd
from openai import OpenAI

API_URL = "https://clovastudio.stream.ntruss.com/v1/openai"
API_KEY = os.environ["CLOVA_API_KEY"]

client = OpenAI(
    api_key=API_KEY,
    base_url=API_URL
)

# Load rubric from Excel
rubric_df = pd.read_excel("Criteria.xlsx")
rubric_lookup = {
    row["Key Questions"].strip(): row["Rubric"].strip()
    for _, row in rubric_df.iterrows()
    if pd.notna(row["Key Questions"]) and pd.notna(row["Rubric"])
}

def evaluate_answer(question, answer):
    model = "HCX-005"

    rubric = rubric_lookup.get(question.strip(), "해당 질문에 대한 평가 기준이 명확하지 않습니다.")

    system_prompt = (
        "당신은 Naver Cloud의 MSP들을 평가할 역량이 있는 전문적인 평가자입니다. 아래 'Interview Result'는 특정 Key question에 대한 요약된 응답이며, "
        "이를 기반으로 Key question에 적절히 답변했는지를 1~5점으로 평가해 주세요."

        f"점수는 다음을 기준으로 공정하고 일관되게 부여해야 합니다:\n\n"
        f"Rubric 기준:\n{rubric}\n\n"

        "**주의사항: (우선적으로 반드시 엄수)**"
        "Interview Result는 해당 회사의 직접적인 응답이 아니라, 나 본인이 인터뷰 내용을 요약한 것입니다. 따라서 표현이 불완전하거나 구체적인 수치가 부족하더라도, 절대로 그것만으로 점수를 낮게 매겨서는 안 됩니다."
        "따라서 오탈자, 구체적 숫자의 부재 등의 형식적 결함에는 **어떠한 불이익도 주어서는 안 됩니다.**"
        "응답이 명확하게 긍정적인 답변을 보여주고, 질문에서 이상적인 답변으로 요구하는 표현이나 경험을 전달한다면, 구체적인 예시가 부족해도 4점 또는 5점으로 평가해 주세요."
        "예시가 부족하거나 불완전하더라도 전반적인 평가가 우수하면 높은 점수를 부여해야 합니다. 전반적인 평가가 부정적이라면 낮은 점수를 부여하세요."

        "**특수 상황에 대한 평가 지침**"
        "언제나 컨텍스트에 맞추어 평가하세요. 예를 들어, 명확한 답변을 요구하는 질문에서 뚜렷하지 않다는 답변은 부정적으로 계산하세요. 반대로 현재 구체적인 성과가 없거나 부족하지만 명확한 개선 의지를 보여준 사례가 있다면 긍정적으로 반영하세요."
        "특정 활동이 보편적인 기대 수준에는 미치지 않더라도, 해당 회사의 상황이나 환경을 고려했을 때 눈에 띄는 노력이나 성과가 있다고 판단된다면, 반드시 일반적인 기준보다 높은 점수를 부여해 주세요."
        "예를 들어, 일반적으로는 현장 인력이 필요한 활동을 즉각 대처 가능한 24시간 유선 운영 등으로 효과적으로 대체하고 있다면, 이는 창의적인 방식으로 높은 성과를 낸 것으로 판단하여 반드시 5점을 부여해 주세요."

        "**예시**"
        "- AI 관련 분야(머신러닝, 딥러닝, 자연어 처리 등) 전문 인력 구성 비율은 어느 정도인가? - 전체 개발인력 20-30명 중 AI 전문인력(모델러)은 5~6명. 5~6명을 제외한 나머지 개발인력도 엔지니어링, 데이터 분석 등 가능. "
        "당사 측에서는 5~6명만 AI 전문인력이라고 표현했으나, 크게 보면 우리 입장에선 20~30명 모두 AI 인력이라고 봐도 괜찮아보임 -> 전체 인력에서 전문 인력의 비율이 적당히 우수한 편이므로 4점"
        "- AI 관련 국내외 자격증 또는 인증을 보유한 인력이 있나요? - AI 분야에서는 자격증이 큰 의미가 없어 별도로 자격증을 딴 사람은 없으나, 위에서 언급한 AI 전문 인력 5~6명은 AI 석박사 학위 보유, 또한 당사에 재직하면서 논문이나 챌린지에서 수상한 이력 존재(당사 홈페이지에서 구체적인 챌린지명 확인 가능) -> 풍부한 석박사 학위와 수상 이력으로 5점"
        "- 팀 내 협업과 지식 공유를 위해 어떤 시스템이나 방법론을 활용하고 있나요? - Jira와 Comfluence의 기능을 합친 느낌의 협업툴(이름 언급X)을 전사적으로 사용하며, 내부 생산성 향상에 기여 -> 결과적으로 생산성 향상이라는 궁극적인 긍정적 표현으로 5점"
        "- AI 전문가, 도메인 전문가, 비즈니스 팀 간의 원활한 협업을 위한 귀사의 접근 방식은 무엇인가요? - AI 전문가와 도메인 전문가, 비즈니스 팀의 연결고리 역할을 수행하는 게 PM이며, 로민은 2인 PM 제도로 운영함. 한 명은 내부 개발 PM, 한 명은 외부 PM. 내부 개발 PM은 비즈니스 팀과 주로 소통하고 외부 PM은 도메인 전문가들과 주로 소통하는 듯함. "
        "또한 당사 아이템인 문서 OCR AI 특성 상, 문서를 잘 인식하려면 그 문서를 이해해야하므로, 해외 서류나 제조업의 경우 문서를 이해하는 데 많은 시간을 할애하고, 필요에 따라 세미나 등 집체 교육을 한 경험도 존재. -> 명확한 시스템, 확실한 개선 의지와 노력으로 5점"
        "- AI 전문가, 도메인 전문가, 비즈니스 팀 간의 원활한 협업을 위한 귀사의 접근 방식은 무엇인가요? - 공식적인 방법론은 부재하나, 소거법으로 도메인이 문제인지 LLM이 문제인지 파악해보며 양쪽의 의견을 절충하는 식으로 트러블을 슈팅하며 문제 해결 -> 방법론의 부재가 있으나 개선 의지가 보이므로 3점"
        "- AI 관련 국내외 자격증 또는 인증을 보유한 인력이 있나요? - AI 관련 자격증에 어떤 게 있는지조차 모름 -> 1점"
        "등이 있습니다."
        "답변은 **숫자 하나로만** 해주세요. 예: 4"

        "최종 판단 시 항상 회사의 맥락과 노력의 질을 고려하세요. 정량적 수치의 부족이나 형식적 결함보다는, 실제로 얼마나 의미 있는 성과나 시스템을 갖추었는지가 핵심입니다."
    )

    user_prompt = f"[질문] {question}\n[응답] {answer}\n점수만 숫자로 알려주세요. (1~5 중 하나) 최종적으로 점수를 매기기 전에 왜 그렇게 매겼는지 상세히 재고하나 반드시 숫자만 기록해 주세요."

    attempt = 0
    while True:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                top_p=0.8,
                max_tokens=10
            )
            content = response.choices[0].message.content.strip()
            if content in {"1", "2", "3", "4", "5"}:
                return int(content)
            else:
                print(f"⚠️ Unexpected response format: '{content}'")
                return f"Unexpected response: {content}"
        except Exception as e:
            wait = min(60, 2 ** attempt + random.uniform(0.5, 1.5))
            print(f"⚠️ CLOVA error: {e}. Retrying in {wait:.2f}s...")
            time.sleep(wait)
            attempt += 1