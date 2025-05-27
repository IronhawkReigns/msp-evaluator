MSP Evaluator

Naver Cloud Platform의 AI & Hybrid Consulting 프로젝트로 개발된 클라우드 MSP(Managed Service Provider) 자동 평가 도구입니다.

인터뷰 기반의 평가 과정을 자동화하고, 평가 데이터를 저장 및 관리할 수 있도록 설계되었습니다.
1단계(GitHub Actions 기반 자동화)와 2단계(Vector DB + FastAPI 기반 인터랙티브 시스템)로 구성되어 있습니다.

⸻

프로젝트 개요

1단계 – 수작업 평가 자동화 (Batch 방식)
	•	트리거: Google Sheet의 “A3” 셀에 “RUN” 입력
	•	동작: GitHub Actions에서 평가 스크립트 실행
	•	결과: 평가 점수가 Google Sheet에 자동 기록
	•	기술 스택: Google Apps Script, GitHub Actions, Python

2단계 – Vector DB 및 웹 기반 UI
	•	트리거: “B3”에 회사명 입력 후 “B4”에 “RUN” 입력
	•	동작: FastAPI 서버 호출, 벡터 DB에 평가 결과 저장
	•	웹 UI: 저장된 MSP 평가 내용을 조회, 검색, 삭제 가능
	•	고급 검색 기능(선택 시): Perplexity Claude API 활용한 웹 기반 검색
	•	PDF 다운로드 기능: 결과 및 근거 데이터를 PDF 리포트로 저장 가능
	•	기술 스택: FastAPI, ChromaDB, SentenceTransformers, Google Sheets API, HTML/JS UI, Perplexity API

⸻

시스템 구성

GitHub Actions (1단계)
	•	GOOGLE_SHEET_CREDENTIALS_JSON GitHub Secrets에 등록 필요
	•	Google Sheet “A3”에 “RUN” 입력 시 자동 실행
	•	main.py:
	•	인터뷰 데이터를 Google Sheet에서 읽음
	•	평가 로직 수행 후 점수를 다시 Sheet에 기록

FastAPI 서버 (2단계)
	•	Naver Cloud VM에 FastAPI + ChromaDB 구성
	•	엔드포인트:
	•	POST /run/{msp_name} → 해당 MSP 데이터를 DB에 삽입
	•	GET /ui → 저장된 데이터를 웹 UI로 시각화
	•	DELETE /ui/delete_company/{msp_name} → 특정 회사의 전체 데이터 삭제
	•	POST /generate_pdf → 평가 결과 및 근거 데이터를 PDF로 생성

Google Apps Script
	•	Google Sheet 편집 감지 트리거 사용
	•	“Automation” 시트에서 아래 두 흐름 실행:
	•	“A3” 입력: GitHub 평가 트리거
	•	“B3” + “B4” 입력: FastAPI 평가 트리거

⸻

AI 평가 로직
	•	Fine-tuning된 LLM (HyperCLOVA 또는 Claude)
	•	15개의 고정 질문에 대해 1~5점 점수 산출
	•	SentenceTransformer로 임베딩 → ChromaDB에 벡터 저장
	•	정보 요청 시 Claude (Perplexity API)를 통해 최신 웹 기반 정보로 응답

⸻

웹 UI
	•	접속 주소: http://mspevaluator.duckdns.org/ui
	•	주요 기능:
	•	저장된 모든 MSP 데이터 테이블 형태로 보기
	•	회사명 또는 질문으로 검색 및 필터링
	•	특정 회사 데이터 일괄 삭제 가능
	•	고급 검색 기능 (웹 검색 기반)
	•	예시 질문 자동 입력 패널
	•	“왜 이 답변인가요?” 버튼을 통해 근거 Q&A 확인
	•	결과 PDF 저장 기능

⸻

주요 파일 설명

파일명	설명
main.py	GitHub Actions에서 사용되는 평가 스크립트
vector_writer.py	평가 결과를 벡터 DB에 삽입하는 로직
api_server.py	FastAPI 서버: UI, 삽입, 삭제, PDF 생성 API 포함
msp_core.py	평가 및 요약 로직, Claude/CLOVA API, PDF 생성 포함
static/index.html	웹 UI 페이지
.github/workflows/evaluate.yml	GitHub Actions 워크플로우
Code.gs	Google Apps Script (트리거 및 API 호출 담당)


⸻

환경변수 / 시크릿 구성

변수명	용도
GOOGLE_SHEET_CREDENTIALS_JSON	Google Sheet API 접근 키
INTERVIEW_SHEET_DOC_NAME	평가 대상 스프레드시트 문서 이름
INTERVIEW_SHEET_NAME	평가 대상 시트 이름
CLOVA_API_KEY	CLOVA API 키 (선택적)
PPLX_API_KEY	Perplexity Claude API 키 (고급 검색용)
GITHUB_TOKEN	GitHub Actions 트리거용 인증 토큰
ADMIN_USERNAME, ADMIN_PASSWORD	관리자 로그인 인증 정보


⸻

유의사항
	•	벡터 DB에서 id가 중복되면 삽입이 실패할 수 있음 (예: 동일 질문 hash)
	•	Google Apps Script 외부 호출(UrlFetchApp.fetch)은 권한 허용 필요
	•	“RUN”을 빠르게 연속으로 입력할 경우 중복 트리거 발생 가능성 있음
	•	Perplexity API는 유료 API이며, 사용량에 따라 요금이 발생할 수 있음

⸻

개발자

신예준 (Yejoon Shin)
Naver Cloud 파트타임
GitHub: IronhawkReigns
이메일: mistervic03@gmail.com / yejoons_2026@gatech.edu

⸻

문의

오류 제보 또는 개선 제안은 GitHub Issue 또는 이메일로 언제든 연락 부탁드립니다.
