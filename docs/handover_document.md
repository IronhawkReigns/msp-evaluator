# MSP 평가 도구 - 개발 인수인계 문서

## 문서 개요

이 문서는 MSP 평가 도구의 완전한 인수인계를 위한 핵심 정보를 담고 있습니다. 신규 담당자가 시스템을 효과적으로 운영하고 개발할 수 있도록 필수 정보와 절차를 제공합니다.

**작성자**: 신예준 (Yejoon Shin)  
**작성일**: 2025년 6월  
**최종 업데이트**: 2025년 6월 30일
**다음 담당자**: [신규 담당자명]

---

## 시스템 개요

### 서비스 정보
- **서비스명**: MSP 평가 도구 (MSP Evaluator)
- **운영 URL**: https://mspeval.org
- **목적**: 클라우드 MSP 파트너사의 AI 역량 자동 평가 및 관리
- **사용자**: NAVER Cloud Platform 내부 팀
- **개발 기간**: 2025년 5월 - 6월

### 핵심 기능
1. **Excel 기반 자동 평가**: HyperCLOVA AI로 1-5점 자동 채점
2. **자연어 검색**: Claude/HyperCLOVA 기반 MSP 추천 시스템  
3. **벡터 검색**: ChromaDB 기반 의미론적 검색
4. **실시간 리더보드**: MSP 파트너사 순위 표시
5. **관리자 대시보드**: 데이터 관리 및 모니터링

### 기술 스택
```
Frontend: React (Vanilla JS), Tailwind CSS, Chart.js
Backend: FastAPI, Python 3.8+
AI/ML: HyperCLOVA, Claude-3, Perplexity
Vector DB: ChromaDB (로컬 설치)
Web Server: Nginx (리버스 프록시)
Deployment: NAVER Cloud Platform Ubuntu VM
SSL: Let's Encrypt (자동 갱신)
```

---

## 시스템 접근 정보

### 서버 접근
```bash
# SSH 접속
ssh ubuntu@[서버_IP_주소]

# 서비스 위치
cd /home/ubuntu/msp-evaluator

# 환경 활성화
source venv/bin/activate
```

### 중요 계정 정보

#### 관리자 계정 (웹 로그인)
- **Username**: 환경변수 `ADMIN_USERNAME` 확인
- **Password**: 환경변수 `ADMIN_PASSWORD` 확인
- **로그인 URL**: http://mspeval.org/login

#### 도메인 설정
- **도메인**: mspeval.org
- **도메인 관리**: 현재 namecheap.com 이용 중, mistervic03@gmail.com 으로 문의


### API 키 관리

#### NAVER HyperCLOVA
```bash
# 환경변수 확인
echo $CLOVA_API_KEY
echo $CLOVA_API_KEY_OPENAI

# 키 위치: NAVER Cloud Platform > AI·Application Service > HyperCLOVA X
# 용도: AI 평가, 벡터 임베딩, 도메인 분류
# 갱신 주기: 필요시 (만료 없음)
```

#### Anthropic Claude
```bash
# 환경변수 확인  
echo $ANTHROPIC_API_KEY

# 키 위치: Anthropic Console (console.anthropic.com)
# 용도: 고급 검색, 정보 요약
# 갱신 주기: 필요시
```

#### Perplexity
```bash
# 환경변수 확인
echo $PPLX_API_KEY  

# 키 위치: Perplexity API 콘솔
# 용도: 웹 기반 고급 검색
# 갱신 주기: 필요시
```

#### NAVER Search API
```bash
# 환경변수 확인
echo $NAVER_CLIENT_ID
echo $NAVER_CLIENT_SECRET

# 키 위치: NAVER Developers (developers.naver.com)
# 용도: 뉴스 검색 기능
# 갱신 주기: 필요시
```


---

## 시스템 구조

### 파일 구조
```
/home/ubuntu/msp-evaluator/
├── api_server.py              # FastAPI 메인 서버
├── msp_core.py               # 검색 엔진 핵심 로직
├── vector_writer.py          # ChromaDB 데이터 관리
├── evaluator.py              # AI 평가 엔진
├── excel_upload_handler.py   # Excel 처리 로직
├── admin_protected.py        # 관리자 인증
├── utils.py                  # 유틸리티 함수
├── clova_router.py          # CLOVA 도메인 분류
├── chroma_store/            # ChromaDB 데이터 (중요!)
├── static/                  # 프론트엔드 파일
│   ├── main.html           # 메인 페이지
│   ├── search.html         # 검색 도구
│   ├── index.html          # 리더보드 (React)
│   ├── upload.html         # 업로드 도구
│   ├── vector-db-viewer.html  # DB 뷰어
│   └── admin.html          # 관리자 대시보드
├── templates/              # Jinja2 템플릿
├── .env                   # 환경변수 (중요!)
├── requirements.txt       # Python 의존성
└── venv/                 # Python 가상환경
```

### 서비스 설정 파일
```bash
# Systemd 서비스
/etc/systemd/system/msp-evaluator.service

# Nginx 설정
/etc/nginx/sites-available/msp-evaluator

# SSL 인증서
/etc/letsencrypt/live/mspeval.org/

# 로그 파일
/var/log/nginx/access.log
/var/log/nginx/error.log
```

---

## 웹 관리자 도구 사용법

### 관리자 대시보드 접근

#### 로그인 절차
```bash
# 1. 브라우저에서 접속
http://mspeval.org/admin

# 2. 로그인 정보 (환경변수에서 확인)
echo $ADMIN_USERNAME  # 사용자명
echo $ADMIN_PASSWORD  # 비밀번호
```

### 주요 관리 기능

#### 1. 실시간 시스템 현황 확인 (/admin)

**대시보드에서 확인할 수 있는 정보**:
- 등록된 MSP 수
- 총 평가 항목 수
- 마지막 업데이트 시간
- ChromaDB 연결 상태

**일일 점검시 확인사항**:
- [ ] MSP 수가 예상 범위 내인지 (급격한 증감 여부)
- [ ] 마지막 업데이트가 24시간 이내인지
- [ ] "ChromaDB 정상 연결됨" 메시지 확인

#### 2. 벡터 DB 관리 (/ui)

**데이터 조회 및 관리**:
- MSP별 평가 데이터 조회
- 중복 데이터 확인
- 손상된 레코드 식별
- 개별 MSP 데이터 삭제

**주간 점검시 수행작업**:
```bash
# 1. 브라우저에서 DB 뷰어 접속
http://mspeval.org/ui

# 2. 다음 사항들 확인
- 중복된 MSP 이름이 있는지 점검
- 비정상적으로 높거나 낮은 점수 (1점 미만, 5점 초과) 확인
- 빈 답변이나 깨진 데이터 확인

# 3. 문제 데이터 발견시 대응
- 중복 데이터: 최신 데이터만 남기고 삭제
- 손상 데이터: "Delete Company" 버튼으로 해당 MSP 전체 삭제 후 재업로드 요청
```

#### 3. 관리자 전용 기능

**데이터 삭제 권한**:
- 벡터 DB 뷰어에서 MSP별 전체 데이터 삭제 가능
- 삭제 전 반드시 백업 확인
- 삭제 후 해당 MSP에게 재업로드 안내

**시스템 설정 변경**:
- API 키 교체: `.env` 파일 수정 후 서비스 재시작
- 최소 점수 기준 조정: 코드 수정 필요시 개발자 연락
- 새로운 평가 카테고리 추가: 개발자 지원 필요

### 관리자 업무 체크리스트

#### 일일 관리 업무 (5분)
- [ ] 관리자 대시보드에서 전체 현황 확인
- [ ] 새로운 에러나 이상 징후 확인
- [ ] 사용자 문의사항 확인 (이메일)

#### 주간 관리 업무 (15분)
- [ ] 벡터 DB 뷰어에서 데이터 품질 점검
- [ ] 중복 또는 손상된 데이터 정리
- [ ] 새로 등록된 MSP 데이터 검토

#### 월간 관리 업무 (30분)
- [ ] 전체 MSP 데이터 검토 및 업데이트 필요성 확인
- [ ] 평가 기준 일관성 점검
- [ ] 사용자 피드백 검토 및 개선사항 도출

### 일반적인 관리 이슈 해결

#### 문제 1: MSP가 자신의 데이터 수정을 요청하는 경우
```bash
# 해결 절차:
1. 벡터 DB 뷰어에서 해당 MSP 데이터 삭제
2. MSP에게 새로운 Excel 파일로 재업로드 요청
3. 업로드 완료 후 데이터 확인
```

#### 문제 2: 검색 결과가 부정확하다는 사용자 신고
```bash
# 확인 절차:
1. 해당 검색어로 직접 테스트 수행
2. 벡터 DB에서 관련 데이터 확인
3. 점수가 비정상적인 데이터가 있는지 점검
4. 필요시 해당 MSP 데이터 재평가 요청
```

#### 문제 3: 새로운 MSP 등록 요청
```bash
# 처리 절차:
1. MSP에게 Excel 템플릿 제공 (user manual 참조)
2. 업로드 페이지 안내: http://mspeval.org/upload
3. 업로드 완료 후 결과 확인 및 피드백 제공
```

### 관리자 권한이 필요한 상황

**즉시 개발자 연락이 필요한 경우**:
- 시스템 전체 장애 (서비스 접근 불가)
- 대량의 데이터 손실
- 보안 관련 이슈 의심
- API 키 대량 만료

**관리자가 직접 처리 가능한 경우**:
- 개별 MSP 데이터 문제
- 사용자 문의 대응
- 일반적인 데이터 품질 관리
- 간단한 사용법 안내

### 데이터 품질 관리 가이드

#### 좋은 데이터의 특징
- 각 질문에 구체적이고 상세한 답변
- 수치와 실제 사례가 포함된 답변
- 평가 점수가 1-5 범위 내
- MSP 이름이 일관되게 표기됨

#### 문제가 있는 데이터
- 동일한 MSP가 다른 이름으로 중복 등록
- 답변이 너무 짧거나 모호함 ("있습니다", "많습니다" 등)
- 평가 점수가 비정상적 (0점 이하, 5점 초과)
- 빈 답변이나 "N/A"가 많은 경우

#### 데이터 정리 기준
```bash
# 삭제 대상 데이터:
- 동일 회사의 중복 데이터 (최신 것만 유지)
- 답변 품질이 현저히 낮은 데이터 (평균 점수 2점 이하)
- 회사명이 명확하지 않은 데이터
- 테스트 목적으로 업로드된 샘플 데이터

# 보존해야 할 데이터:
- 정식으로 평가받은 모든 MSP 데이터
- 점수가 낮더라도 성실하게 답변한 데이터
- 최근 6개월 이내 업데이트된 데이터
```

---

## 일일 운영 가이드

### 매일 확인해야 할 사항

#### 1. 서비스 상태 확인 (09:00)
```bash
# 서비스 가동 상태
sudo systemctl status msp-evaluator
sudo systemctl status nginx

# 응답 테스트
curl -I http://localhost:8000/
curl -I http://mspeval.org/
```

#### 2. 시스템 리소스 확인
```bash
# 디스크 사용량 (80% 이상 시 주의)
df -h

# 메모리 사용량
free -h

# CPU 사용량
top -n 1 | head -5
```

#### 3. 에러 로그 확인
```bash
# 오늘의 에러 수
sudo journalctl -u msp-evaluator --since today | grep -i error | wc -l

# 최근 에러 내용
sudo journalctl -u msp-evaluator --since "1 hour ago" | grep -i error
```

### 주간 작업 (매주 월요일)

#### 1. 백업 확인
```bash
# ChromaDB 백업 실행
cd /home/ubuntu/msp-evaluator
tar -czf "/backup/chromadb_backup_$(date +%Y%m%d).tar.gz" chroma_store/

# 백업 파일 정리 (7일 이상 된 것)
find /backup -name "chromadb_backup_*.tar.gz" -mtime +7 -delete
```

#### 2. 로그 정리
```bash
# 시스템 로그 정리 (14일 보관)
sudo journalctl --vacuum-time=14d

# Nginx 로그 로테이션 확인
sudo logrotate -f /etc/logrotate.d/nginx
```

---

## 긴급 상황 대응

### 서비스 중단 시 복구 절차

#### Step 1: 즉시 대응 (5분 이내)
```bash
# 서비스 재시작
sudo systemctl restart msp-evaluator
sudo systemctl restart nginx

# 상태 확인
sudo systemctl status msp-evaluator
sudo systemctl status nginx
```

#### Step 2: 문제 진단 (10분 이내)
```bash
# 에러 로그 확인
sudo journalctl -u msp-evaluator --lines=50

# 포트 점유 확인
sudo netstat -tlnp | grep :8000

# 디스크 공간 확인
df -h
```

#### Step 3: 복구 시도 (30분 이내)
```bash
# ChromaDB 권한 문제 해결
sudo chown -R ubuntu:ubuntu chroma_store/
chmod 755 chroma_store/

# Python 의존성 재설치 (필요시)
source venv/bin/activate
pip install -r requirements.txt

# 환경변수 확인
cat .env | grep -v "PASSWORD\|SECRET\|KEY"
```

### 데이터 손실 시 복구

#### 백업에서 복원
```bash
# 1. 현재 데이터 백업 (혹시 모를 상황 대비)
mv chroma_store chroma_store_failed_$(date +%Y%m%d_%H%M%S)

# 2. 최신 백업 찾기
LATEST_BACKUP=$(ls -t /backup/chromadb_backup_*.tar.gz | head -1)
echo "복원할 백업: $LATEST_BACKUP"

# 3. 백업에서 복원
tar -xzf "$LATEST_BACKUP"

# 4. 서비스 재시작
sudo systemctl restart msp-evaluator
```

### SSL 인증서 문제

#### 인증서 갱신
```bash
# 인증서 상태 확인
sudo certbot certificates

# 수동 갱신
sudo certbot renew

# Nginx 재시작
sudo systemctl reload nginx
```

### API 키 만료/오류

#### 키 교체 절차
```bash
# 1. .env 파일 백업
cp .env .env.backup

# 2. 새 API 키로 교체
nano .env

# 3. 서비스 재시작 (환경변수 다시 로드)
sudo systemctl restart msp-evaluator

# 4. API 테스트
curl -X POST http://localhost:8000/query/router \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "chat_history": [], "advanced": false}'
```

---

## 핵심 아키텍처 결정사항

### 왜 이 기술들을 선택했는가?

#### HyperCLOVA (vs OpenAI)
**선택 이유:**
- 한국어 최적화된 성능
- NAVER Cloud 생태계 통합
- 기업용 API 지원
- 비용 효율성 (크레딧 기반)

**한계점:**
- 영어 모델 대비 제한적
- API 문서가 상대적으로 부족

#### ChromaDB (vs Pinecone/Weaviate)
**선택 이유:**
- Python 네이티브 통합
- 로컬 설치 가능 (클라우드 비용 절약)
- 간단한 설정과 관리
- 빠른 프로토타이핑

**한계점:**
- 대규모 확장성 제한
- 분산 처리 지원 부족

#### FastAPI (vs Django/Flask)
**선택 이유:**
- 자동 API 문서 생성
- 비동기 처리 지원
- 타입 힌트 기반 검증
- 높은 성능

#### React with Vanilla JS (vs 프레임워크)
**선택 이유:**
- 빠른 개발 (CDN 사용)
- 복잡한 빌드 과정 불필요
- 단순한 배포

**한계점:**
- 대규모 앱에는 부적합
- 상태 관리 복잡성

### 데이터 플로우 이해

#### 1. Excel 업로드 → AI 평가
```
Excel 파일 → excel_upload_handler.py → evaluator.py (HyperCLOVA) → 점수 산정
```

#### 2. 벡터 저장
```
평가 데이터 → vector_writer.py → CLOVA Embedding → ChromaDB 저장
```

#### 3. 자연어 검색
```
사용자 질문 → clova_router.py (도메인 분류) → msp_core.py → 
벡터 검색 → Claude/HyperCLOVA (답변 생성) → 결과 반환
```

---

## 성능 기준 및 모니터링

### Service Level Objectives (SLOs)

#### 가용성
- **목표**: 99% 월간 가용성
- **측정**: HTTP 200 응답 비율
- **임계값**: 주간 95% 미만 시 알림

#### 응답 시간
- **검색 요청**: 95% 요청이 2초 이내
- **Excel 평가**: 95% 요청이 30초 이내  
- **벡터 DB 조회**: 95% 요청이 500ms 이내

#### 동시 사용자
- **지원 규모**: 최대 50명 동시 사용
- **성능 저하**: 50명 초과 시 응답 시간 증가

### 현재 성능 벤치마크
```bash
# API 응답 시간 테스트
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/

# 동시 사용자 테스트 (apache bench)
ab -n 100 -c 10 http://localhost:8000/
```

### 모니터링 대시보드
- **웹 접근**: http://mspeval.org/admin
- **시스템 메트릭**: htop, df -h, free -h
- **로그 모니터링**: journalctl -u msp-evaluator -f

---

## 보안 고려사항

### 인증 및 권한
- **관리자 인증**: FastAPI-Login 기반 쿠키 인증
- **API 보안**: 환경변수 기반 키 관리
- **파일 업로드**: Excel 형식 검증, 크기 제한

### 데이터 보호
- **API 키**: .env 파일에 저장 (git 제외)
- **사용자 데이터**: 최소 수집 원칙
- **백업**: 암호화되지 않음 (민감 정보 없음)

### 네트워크 보안
- **방화벽**: UFW 설정 (80, 443, 22 포트만 열림)
- **SSL**: Let's Encrypt 자동 갱신
- **리버스 프록시**: Nginx로 FastAPI 숨김

### 알려진 보안 취약점
1. **관리자 비밀번호**: 환경변수에 평문 저장
2. **API 키 로그**: 로그에 키가 노출될 가능성
3. **파일 업로드**: 악성 파일 검증 부족

---

## 알려진 이슈 및 해결 방법

### 1. 대용량 Excel 파일 처리 시 타임아웃
**증상**: 50개 이상 질문 시 504 Gateway Timeout
**원인**: HyperCLOVA API 순차 호출로 인한 지연
**해결 방법**:
```python
# evaluator.py에서 배치 처리 구현 (향후 개선사항)
# 또는 Nginx timeout 증가
# /etc/nginx/sites-available/msp-evaluator
proxy_read_timeout 300;
```

### 2. ChromaDB 재시작 후 첫 검색 지연
**증상**: 서비스 재시작 후 첫 검색이 5-10초 소요
**원인**: ChromaDB 인덱스 로딩 시간
**해결 방법**: 정상적인 현상, warm-up 후 빨라짐

### 3. 동시 사용자 50명 이상 시 성능 저하
**증상**: 응답 시간 증가, 메모리 사용량 급증
**원인**: 단일 서버, 메모리 제한
**해결 방법**: 
```bash
# 메모리 부족 시 스왑 활용
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 4. API 키 할당량 초과
**증상**: 429 Too Many Requests 에러
**원인**: API 일일/월간 한도 초과
**해결 방법**: NAVER Cloud Console에서 한도 확인 및 증액 요청

---

## 향후 개발 방향

### 단기 개선 사항 (1-3개월)
- [ ] **성능 최적화**: API 응답 시간 단축 (배치 처리)
- [ ] **오류 처리 개선**: 사용자 친화적 에러 메시지
- [ ] **모니터링 강화**: Prometheus + Grafana 도입
- [ ] **자동 백업**: 일일 자동 백업 스크립트

### 중기 계획 (3-6개월)
- [ ] **다국어 지원**: 영어 인터페이스 추가
- [ ] **고급 분석**: 트렌드 분석, 예측 기능
- [ ] **API 개선**: RESTful API 표준화
- [ ] **보안 강화**: JWT 인증, API 키 암호화

### 장기 비전 (6개월+)
- [ ] **마이크로서비스**: 검색/평가 서비스 분리
- [ ] **클라우드 네이티브**: Kubernetes 배포
- [ ] **ML 파이프라인**: 자동 모델 학습/배포
- [ ] **모바일 앱**: React Native 앱 개발

---

## 연락처 및 지원

### 개발자 정보
**신예준 (Yejoon Shin)**
- **이메일**: mistervic03@gmail.com / yejoons_2026@gatech.edu
- **GitHub**: [IronhawkReigns](https://github.com/IronhawkReigns)
- **응답 시간**: 24시간 이내 (긴급 시 즉시)
- **시간대**: 미국 동부시간 (EST)

### NAVER Cloud Platform 지원
- **지원 포털**: NAVER Cloud Platform Console
- **기술 지원**: 콘솔 내 1:1 문의
- **긴급 상황**: 전화 지원 (유료 서비스)

### 외부 서비스 지원
- **HyperCLOVA**: NAVER Cloud Platform 콘솔
- **Anthropic**: support@anthropic.com
- **Let's Encrypt**: Let's Encrypt 커뮤니티

### 에스컬레이션 절차

#### Level 1: 자동 복구 (5분)
1. 서비스 재시작 시도
2. 기본 진단 스크립트 실행
3. 로그 확인

#### Level 2: 관리자 대응 (30분)
1. 수동 문제 해결 시도
2. 백업에서 복구
3. 개발자 연락

#### Level 3: 전문가 지원 (2시간)
1. 개발자 직접 지원
2. 심층 분석 및 수정
3. 시스템 재구축 검토

---

## 인수인계 체크리스트

### 시스템 접근 확인
- [ ] SSH 서버 접근 가능
- [ ] 관리자 웹 로그인 가능
- [ ] 모든 API 키 작동 확인
- [ ] DuckDNS 도메인 접근 가능

### 기본 운영 숙지
- [ ] 일일 점검 절차 숙지
- [ ] 서비스 재시작 방법 숙지
- [ ] 로그 확인 방법 숙지
- [ ] 백업/복원 절차 숙지

### 웹 관리자 도구 숙지
- [ ] 관리자 대시보드 접속 및 사용법 숙지
- [ ] 벡터 DB 뷰어 사용법 숙지
- [ ] MSP 데이터 삭제 절차 숙지
- [ ] 데이터 품질 관리 기준 이해

### 긴급 상황 대응
- [ ] 서비스 중단 시 복구 절차 실습
- [ ] 데이터 복원 절차 실습
- [ ] SSL 인증서 갱신 실습
- [ ] API 키 교체 절차 실습

### 개발 환경 설정
- [ ] 로컬 개발 환경 구축
- [ ] Git 저장소 접근 확인
- [ ] 코드 수정 및 배포 절차 숙지
- [ ] 테스트 실행 방법 숙지

### 문서 및 리소스
- [ ] 개발자 가이드 숙지
- [ ] 관리자 가이드 숙지
- [ ] 사용자 매뉴얼 숙지
- [ ] API 문서 확인

### 모니터링 및 알림
- [ ] 모니터링 대시보드 접근
- [ ] 알림 설정 확인
- [ ] 성능 지표 이해
- [ ] 로그 분석 도구 사용법

---

## 추가 참고 자료

### 프로젝트 문서
- [MSP 평가 도구 - 개발자 가이드](./msp_developer_guide.md)
- [MSP 평가 도구 - 사용자 매뉴얼](./msp_user_manual.md)

### 기술 문서
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [ChromaDB 공식 문서](https://docs.trychroma.com/)
- [HyperCLOVA X API 가이드](https://www.ncloud.com/product/aiService/clovaStudio)
- [Anthropic Claude API](https://docs.anthropic.com/)

### 인프라 관리
- [NAVER Cloud Platform 콘솔](https://console.ncloud.com/)
- [Let's Encrypt 문서](https://letsencrypt.org/docs/)
- [Nginx 설정 가이드](https://nginx.org/en/docs/)
- [Ubuntu 서버 관리](https://ubuntu.com/server/docs)

---

**관리자 도구 관련 문의사항은 개발자에게 연락: mistervic03@gmail.com**

**이 문서는 MSP 평가 도구의 완전한 인수인계를 위해 작성되었습니다. 추가 질문이나 불명확한 부분이 있으면 언제든 개발자에게 연락해 주세요.**

*마지막 업데이트: 2025년 6월*
