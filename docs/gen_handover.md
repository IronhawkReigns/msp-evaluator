# MSP 평가 도구 - 개발자 인수인계 노트

## 먼저 읽어 주세요

이 문서는 공식 PDF 인수인계 문서보다 가볍고 실용적인 목적으로 작성된 개발자 중심 노트입니다.  
다음 개발자 분이 시스템을 유지하거나 새로운 방향으로 확장할 때 도움이 될 수 있는 실전 정보와 제안을 담고 있습니다.

---

## 추천 배포 방식

현재 MVP (minimum viable product) 버전은 제 NCP 서브 계정에서 정상적으로 운영 중입니다. 다만, **운영 안정성과 소유권 명확성을 위해** 아래와 같은 배포 방식을 권장드립니다:

- GitHub 저장소의 **main 브랜치** 기준으로
- 새로운 NCP 서브 계정이나 VM에서 직접 재배포
- 저의 서버는 *레퍼런스 용도*로만 일정 기간 유지될 수 있음

🔗 GitHub 저장소: [github.com/IronhawkReigns/msp-evaluator](https://github.com/IronhawkReigns/msp-evaluator)  
✅ `.env.example` 포함되어 있습니다. `.env` 파일로 복사 후 API 키만 채워주시면 됩니다.

---

## 제가 맡았던 범위

2025년 5~6월 동안 제가 맡은 개발 범위는 다음과 같습니다:

- 전체 평가 시스템 기획 및 FastAPI 백엔드 개발
- Excel 업로드 자동 채점 파이프라인 구현 (HyperCLOVA 기반)
- 자연어 검색 기반 MSP 추천 시스템 (Claude + CLOVA)
- 관리자 리더보드, 데이터 뷰어 UI (React, Tailwind CSS)
- 시스템 배포 (Nginx + Systemd + Let's Encrypt SSL)
- 인프라 세팅 및 보안 구성 (NCP Ubuntu VM)

---

## 어디까지 구현되었는가?

| 기능 | 구현 여부 | 비고 |
|------|-----------|------|
| Excel 업로드 자동 평가 | ✅ | HyperCLOVA 사용 |
| 자연어 기반 MSP 검색 | ✅ | Claude + CLOVA 기반 |
| 고급 정보 검색 기능 | ✅ | Perplexity API 연동 |
| 리더보드 UI | ✅ | 점수 및 카테고리별 정렬 |
| 관리자 페이지 및 DB 뷰어 | ✅ | `/admin`, `/ui` 경로 |
| ChromaDB 백업 스크립트 | ✅ | 일일 수동 또는 자동 실행 가능 |

---

## 이후 계획 또는 개선 아이디어 (개인적인 제안)

- **Claude 비용 절감을 위한 캐싱** (e.g. LRU 기반)
- **LLM 답변 품질 향상**: 사용자 피드백 기반 재평가 흐름 설계
- **고급 통계 뷰어**: 평가 점수 변화 추이 시각화
- **Qdrant 등 외부 벡터 DB로 마이그레이션 고려**
- **Admin UI 개선**: 더 직관적인 UX, 검색 기능 추가
- **PostgreSQL 기반 RDS 구조 도입**:  
  - 정형 데이터(RDS) + 비정형 데이터(ChromaDB) 분리 구조 설계  
  - 회사명, 총점, 카테고리 점수는 RDS에 저장  
  - 자연어 응답은 ChromaDB 유지 → 필터링/정렬/검색 최적화 가능

---

## 배포 시 주의사항

- `.env` 경로 오류 → API 키 로딩 실패 → AI 기능 모두 비활성화됨
- `chroma_store` 폴더가 비어 있으면 `/query/router`에서 결과 없음
- Nginx 캐시로 인해 React UI 변경사항이 반영 안 되는 경우 있음 → 강제 새로고침 필요

---

## Claude 평가 프롬프트 구조 요약

- `/query/router` → 사용자의 자연어 질의 입력
- Claude 프롬프트에 삽입되어 MSP 추천 + 평가 항목 근거 리스트 생성
- Prompt는 다음 기준을 따름:
  - 15개 평가 질문 중 관련성 높은 질문 추출
  - 각 항목에 대해 `점수`, `이유`, `회사명`을 포함한 structured format 반환
  - `evaluator.py` 내부에서 로직 조정 가능

---

## 로그 메시지 해석 팁

- `[ERROR] Failed to generate embedding` → CLOVA API 키 문제 또는 한도 초과
- `[ERROR] Cannot connect to ChromaDB` → 디렉토리 권한 문제 (`chown`으로 해결)
- `[ERROR] Process killed` → 메모리 부족 (스왑 파일 설정으로 해결 가능)

---

## 건드려도 되는 것 vs 조심할 것

| 항목 | 설명 |
|------|------|
| ✅ `venv/` | 재생성 가능 (서버 재설치 시 새로 구성하면 됨) |
| ✅ `static/` 내 일부 HTML | React UI와 무관한 페이지 있음 (혼동 주의) |
| ⚠️ `.env` | 절대 커밋 금지, 키 유출 주의 |
| ⚠️ `chroma_store/` | 삭제 전 백업 필수 (데이터 모두 날아감) |

---

## 개인적인 팁 몇 가지

- **에러 났을 때** `sudo journalctl -u msp-evaluator -f` 로 로그 확인하는 게 가장 빠릅니다
- `/query/router` 에 Claude 연결돼 있어서, API limit 나면 그쪽부터 확인해보세요
- `.env` 잘못되면 조용히 실패합니다… 무조건 재확인!
- 클로바 임베딩은 **오류가 있어도 조용히 None 리턴**할 수 있어서, `chroma_store` 비면 이쪽부터 의심하세요
- Claude + Perplexity 호출은 고비용이므로, 디버깅할 땐 `advanced=false`로 테스트 권장

---

## 마지막으로

운영하시다가 이슈가 생기거나 구조 이해가 어려울 경우, 부담 없이 연락 주세요.  
필요시 단발성 코드 설명이나 방향성 조언도 도와드릴 수 있습니다.

📧 mistervic03@gmail.com  
⏰ 미국 동부/한국 시간대 모두 대응 가능

새로운 운영자 분의 손에서 이 도구가 더 발전하길 바랍니다!

— 신예준 드림
