# MSP Evaluator

Naver Cloud Platform의 AI & Hybrid Consulting 프로젝트로 개발된 클라우드 MSP(Managed Service Provider) 자동 평가 도구입니다.

인터뷰 기반의 평가 과정을 자동화하고, 평가 데이터를 저장 및 관리할 수 있도록 설계되었습니다.  
1단계(GitHub Actions 기반 자동화)와 2단계(Vector DB + FastAPI 기반 인터랙티브 시스템)로 구성되어 있습니다.

---

## 프로젝트 개요

### 1단계 – 수작업 평가 자동화 (Batch 방식)

- **트리거**: Google Sheet의 `A3` 셀에 `"RUN"` 입력
- **동작**: GitHub Actions에서 평가 스크립트 실행
- **결과**: 평가 점수가 Google Sheet에 자동 기록
- **기술 스택**: Google Apps Script, GitHub Actions, Python

### 2단계 – Vector DB 및 웹 기반 인터랙티브 UI

- **트리거**: `"B3"`에 회사명 입력 → `"B4"`에 `"RUN"` 입력
- **동작**: FastAPI 서버가 Google Sheet 데이터를 임베딩 후 ChromaDB에 저장
- **웹 UI**: 자연어 질의 → MSP 자동 추천 또는 정보 요약 응답
- **기술 스택**: FastAPI, ChromaDB, SentenceTransformers, HyperCLOVA, Perplexity Claude, HTML/JS UI

---

## 시스템 구성

### GitHub Actions (1단계)

- `GOOGLE_SHEET_CREDENTIALS_JSON` GitHub Secrets에 등록 필요
- Google Sheet `"A3"`에 `"RUN"` 입력 시 자동 실행
- `main.py`:
  - 인터뷰 데이터를 Google Sheet에서 읽음
  - 평가 로직 수행 후 점수를 다시 Sheet에 기록

### FastAPI 서버 (2단계)

- Naver Cloud VM에 FastAPI + ChromaDB 구성
- 주요 엔드포인트:
  - `POST /run/{msp_name}` → 해당 MSP 데이터를 DB에 삽입
  - `POST /query/router` → 자연어 질의 처리 (도메인 분류 + 추천/정보요약)
  - `POST /generate_pdf` → AI 응답 및 평가 근거 PDF로 생성
  - `GET /ui` → 저장된 데이터를 웹 UI로 시각화
  - `GET /ui/data` → 질문별 결과 목록 반환
  - `DELETE /ui/delete_company/{msp_name}` → 특정 회사 데이터 삭제

### Google Apps Script

- Google Sheet 편집 감지 트리거 사용
- `"Automation"` 시트에서 아래 두 흐름 실행:
  - `"A3"` 입력 → GitHub 평가 트리거
  - `"B3"` + `"B4"` 입력 → FastAPI 평가 트리거

---

## AI 평가 로직

- Fine-tuning된 LLM (HyperCLOVA 또는 Claude)
- 15개의 고정 질문에 대해 1~5점 점수 산출
- SentenceTransformer로 임베딩 → ChromaDB에 벡터 저장
- 고급 검색 활성 시 Claude의 웹 기반 지식까지 활용
- 평가 방식:
  - **Information**: 특정 MSP 관련 정보 요약
  - **Recommendation**: 여러 MSP 중 질문에 가장 부합하는 상위 2개 추천
- 벡터 기반 추천 근거(질문/답변/점수) 표시 지원

---

## 웹 UI

- 접속 주소: [`http://mspevaluator.duckdns.org/ui`](http://mspevaluator.duckdns.org/ui)
- 주요 기능:
  - 저장된 모든 MSP 평가 데이터 확인
  - 자연어 질문 → AI 응답 및 MSP 추천/요약
  - **예시 질문 패널**: 클릭만으로 테스트 가능
  - **왜 이 답변인가요?**: 벡터 기반 근거 질문/답변/점수 표시
  - **PDF로 저장**: AI 응답과 해당 평가 근거 PDF로 다운로드
  - 고급 검색: Perplexity Claude를 통한 웹 기반 지식 요약 (선택적)
  - 회사명, 질문 기준 필터링
  - 특정 MSP 데이터 일괄 삭제

---

## 주요 파일 설명

| 파일명               | 설명                                                      |
|----------------------|-----------------------------------------------------------|
| `main.py`            | GitHub Actions에서 사용되는 평가 스크립트                 |
| `vector_writer.py`   | 평가 결과를 벡터 DB에 삽입하는 로직                       |
| `api_server.py`      | FastAPI 서버: UI, 삽입, 삭제, 자연어 처리, PDF API 포함   |
| `msp_core.py`        | 자연어 질의 처리, CLOVA/Claude 응답 및 임베딩 로직        |
| `static/index.html`  | UI 웹페이지 (Query 인터페이스 포함)                       |
| `static/query.js`    | 검색 실행, 예시 질문 버튼, 고급 토글 등 클라이언트 로직   |
| `.github/workflows/evaluate.yml` | GitHub Actions 자동화 트리거                     |
| `Code.gs`            | Google Apps Script (Google Sheet 이벤트 핸들링)            |

---

## 환경변수 / 시크릿 구성

| 변수명                     | 용도                                      |
|----------------------------|-------------------------------------------|
| `GOOGLE_SHEET_CREDENTIALS_JSON` | Google Sheet API 접근 키            |
| `INTERVIEW_SHEET_DOC_NAME` | 평가 대상 스프레드시트 문서 이름         |
| `INTERVIEW_SHEET_NAME`     | 평가 대상 시트 이름                      |
| `CLOVA_API_KEY`            | CLOVA Studio API 키                        |
| `PPLX_API_KEY`             | Perplexity Claude API 키 (선택)           |
| `GITHUB_TOKEN`             | GitHub Actions 트리거용 인증 토큰         |
| `ADMIN_USERNAME`           | 관리자 로그인 ID                          |
| `ADMIN_PASSWORD`           | 관리자 로그인 비밀번호                    |

---

## 유의사항

- ChromaDB에서 동일한 ID(예: 같은 질문 hash) 존재 시 삽입 실패할 수 있음
- Google Apps Script의 외부 API 호출 시 권한 허용 필요
- 평가 트리거 `"RUN"`은 일정 간격을 두고 입력해야 중복 실행 방지 가능
- Perplexity 사용 시 요금이 발생할 수 있음 (클라우드 과금 주의)

---

## 개발자

**신예준 (Yejoon Shin)**  
Naver Cloud Platform 파트타임  
GitHub: [IronhawkReigns](https://github.com/IronhawkReigns)  
이메일: mistervic03@gmail.com / yejoons_2026@gatech.edu

---

## 문의

오류 제보 또는 개선 제안은 [GitHub Issue](https://github.com/IronhawkReigns/msp-evaluator/issues)  
또는 이메일로 연락 주세요.
