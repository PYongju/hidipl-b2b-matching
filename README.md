# 하이디플 B2B 매칭 시스템

> AV·디스플레이 장비 조달 컨설팅을 위한 AI 견적 비교·추천 시스템 — Teamprism × 하이디플(HIDIPL) 캡스톤 프로젝트
> 

고객의 견적 요청사항과 파트너사 견적서를 구조화한 뒤, **요구사항-견적서 유사도**와 **가격·납기·보증·설치 조건**을 기준으로 Top-N 견적서를 추천하고, 그 추천 사유를 LLM으로 생성해 주는 시스템입니다.

## 1. 주요 기능

- **시공사/공급사 매칭** — 요구사항 임베딩과 파트너사 프로필 임베딩 기반 후보 선정
- **견적 비교 대시보드** — 가격·납기·보증·설치 조건을 한눈에 비교하는 비교표
- **AI 근거 생성** — Azure OpenAI(gpt-4.1-mini) 기반 추천 사유 및 공급사 장단점 요약

## 2. 추천 파이프라인

```
고객 요청 입력
  └─> RequirementIngestionPipeline ─> RequirementInfo + requirement_embedding

견적서 업로드 (PDF/이미지: Azure OCR, Excel: 직접 파싱)
  └─> QuoteIngestionPipeline ─> QuoteDocument + vendor_snapshot + quote_embedding

견적서 비교/랭킹
  └─> RecommendationPipeline ─> Top 3 추천 결과

추천 사유 생성
  └─> ExplanationProvider ─> AI 근거 요약 / 공급사 장단점
```

## 3. 기술 스택

| 구분 | 스택 |
| --- | --- |
| Frontend | React 19, Vite, Tailwind CSS v4 |
| Backend | Python, FastAPI, SQLAlchemy, Uvicorn |
| Database | MariaDB (PyMySQL) |
| AI / ML | Azure Document Intelligence, Azure OpenAI (Embedding · Chat) |
| Infra | Docker, docker-compose |

## 4. 디렉터리 구조

```
hidipl-b2b-matching/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 진입점
│   │   ├── api/v1/routes.py         # API 라우트 (+ DB 연동, Bearer 토큰 인증)
│   │   ├── core/
│   │   │   ├── database.py          # DB 세션
│   │   │   └── auth.py              # Entra ID 토큰 검증 (verify_token)
│   │   ├── config/paths.py          # 공통 경로 상수
│   │   └── services/                # 핵심 도메인 파이프라인
│   │       ├── requirement_ingestion/ quote_ingestion/
│   │       ├── parser/ ocr/ embedding/ similarity/
│   │       ├── ranking/ recommendation/ partner_matching/
│   │       ├── explanation/
│   │       └── api_demo/            # 테스트용 데모 API
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                        # React + Vite 대시보드
│   └── src/
│       ├── auth/                    # MSAL 인증 (msalConfig.js, msalInstance.js)
│       ├── api/                     # apiClient.js (Bearer 토큰 자동 주입)
│       ├── pages/
│       ├── components/
│       ├── hooks/
│       ├── utils/
│       ├── data/
│       └── assets/
├── database/init.sql                # MariaDB 스키마 (handover v1.4)
├── docs/
└── docker-compose.yml
```

## 5. 실행 방법

### 5.1 Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 환경변수(.env)를 backend/app 루트에 생성한 뒤 실행
cd app
uvicorn main:app --reload --port 8000
```

> 백엔드 실행 기준 루트는 `backend/app` 입니다. 공통 경로는 `backend/app/config/paths.py`에서 관리합니다.
> 

### 5.2 Frontend

```bash
cd frontend
npm install
cp .env.example .env              # VITE_API_BASE_URL / VITE_USE_MOCK_API 설정
npm run dev
```

> `VITE_USE_MOCK_API=true`(기본값)이면 실제 백엔드 없이 mock 데이터로 동작합니다. 실제 API 호출 시 `VITE_USE_MOCK_API=false` + `VITE_API_BASE_URL` 설정이 필요합니다.
> 

### 5.3 Docker

```bash
docker-compose up --build
```

## 6. 환경변수

`.env` 파일은 Git에 포함하지 않습니다. `.env.example`을 참고해 로컬에서 생성하세요.

```
# Azure Document Intelligence
DOCUMENTINTELLIGENCE_ENDPOINT=
DOCUMENTINTELLIGENCE_API_KEY=
OCR_PROVIDER=azure
AZURE_DOCUMENT_MODEL_ID=prebuilt-layout

# Azure OpenAI Embedding
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=embedding-3-large
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Azure OpenAI Chat
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_CHAT_API_VERSION=2025-01-01-preview

#================db 세팅===================
DB_HOST=20.196.73.17
DB_PORT=3306
DB_NAME=hidipl
DB_USER=hidipl
DB_PASSWORD=hidipl123

API_DEMO_STORE_PERSISTENCE=mysql_json

#=======로그인 엔드포인트==============
AZURE_TENANT_ID=5fb256f0-fbf2-40d2-81d5-bac1b32c419d
AZURE_CLIENT_ID=7f8965c5-bf57-469a-871f-d8d24bad4ced
```

## 7. API 개요

| Method | Endpoint | 설명 |
| --- | --- | --- |
| POST | `/api/v1/projects` | 고객 요청 등록 |
| POST | `/api/v1/projects/{project_id}/quotes` | 견적서 업로드 + OCR/파싱 |
| POST | `/api/v1/projects/{project_id}/matches` | 견적서 Top-N 추천 실행 |
| GET | `/api/v1/projects/{project_id}/matches` | 추천 결과 조회 |
| GET | `/api/v1/projects/{project_id}/matches/{match_id}/explanation` | AI 추천 사유 조회 |
| POST | `/api/v1/projects/{project_id}/compare` | 견적 비교표 생성 |

## 8. 테스트

```bash
cd backend/app
python -m services.test_requirement_ingestion_pipeline
python -m services.test_quote_ingestion_pipeline
python -m services.test_recommendation_pipeline
python -m services.test_explanation_provider
python -m services.test_api_demo_flow

# 전체 데모 흐름
python -m services.test_full_pipeline_demo
```

## 9. 평가 지표 (Evaluation)

본 시스템의 핵심 AI 기능은 정량 지표로 검증한다. baseline 대비 개선을 기준으로 한다.

| 기능 | 지표 | Baseline | 현재 | 비고 |
| --- | --- | --- | --- | --- |
| 견적서 Top-N 추천 | Recall@3 | (측정 예정) | (측정 예정) | 정답 견적서가 Top3에 포함되는 비율 |
| 견적서 Top-N 추천 | MRR | (측정 예정) | (측정 예정) | 정답 순위의 역수 평균 |
| 공급사 매칭 | Precision@K | (측정 예정) | (측정 예정) | 후보 공급사 정확도 |
| OCR 파싱 | 필드 추출 정확도 | (측정 예정) | (측정 예정) | 가격·납기·보증 필드 기준 |

> 평가용 데이터셋·정답 라벨 구성 방식은 `docs/`에 별도 기록한다. (작성 예정)
> 

## 10. Azure 비용 (Cost)

본 시스템은 아래 Azure 리소스에서 호출 단위 과금이 발생한다.

| 리소스 | 과금 단위 | 호출 시점 |
| --- | --- | --- |
| Azure Document Intelligence (prebuilt-layout) | 페이지당 | 견적서 PDF/이미지 업로드 시 |
| Azure OpenAI Embedding (embedding-3-large) | 토큰당 | 요청·견적서 임베딩 생성 시 |
| Azure OpenAI Chat (gpt-4.1-mini) | 토큰당 | AI 추천 사유 생성 시 |
- 월 예상 호출량 및 단가 추정: (용주/지우 확정 예정)
- 비용 절감 옵션: 임베딩 결과를 DB에 캐싱해 재요청 시 재호출을 막는다(quote_embedding 저장). 동일 견적서 재처리 시 OCR/임베딩 생략.

## 11. 한계 및 알려진 이슈 (Limitations)

- LLM(gpt-4.1-mini)은 추천 **사유 생성** 보조용이며, 추천 순위 자체는 임베딩 유사도·규칙 기반 랭킹이 결정한다. LLM이 순위를 바꾸지 않는다.
- OCR 정확도는 견적서 양식 편차에 영향을 받는다. 비정형 양식은 수동 검수가 필요할 수 있다.
- 현재 매칭은 (측정 예정) 건 규모의 데이터로 검증되었다.

## 12. 인계 가이드 (Handover)

> 본 저장소는 캡스톤 프로젝트 산출물이며, 하이디플(HIDIPL) 인계를 2차 산출물로 합니다.
> 
- DB 스키마: `database/init.sql` (handover v1.4) 기준.
- 환경변수: `.env.example` 복사 후 Azure 키 6종 입력 필요.
- 핵심 진입점: `backend/app/main.py`, 도메인 로직은 `backend/app/services/` 하위 파이프라인.
- 인계 운영·법적 검토 담당: 수현.

## 13. 트러블슈팅

- **백엔드 import 오류**: 실행 루트가 `backend/app` 인지 확인 (`uvicorn main:app`).
- **프론트가 데이터를 못 받음**: `VITE_USE_MOCK_API=false` 및 `VITE_API_BASE_URL` 설정 확인.
- **Azure 401/403**: `.env`의 엔드포인트·API 버전 문자열 확인 (Embedding/Chat은 API 버전이 다름).

## 14. 팀 (Teamprism)

| 이름 | 역할 |
| --- | --- |
| 유리 | PO / 팀장 / 프론트엔드 리드 |
| 지원 | PM / 클라이언트 커뮤니케이션 |
| 용주 | 백엔드 · 도메인 리드 |
| 호진 | ML · 추상화 리드 |
| 은민 | UX · 프론트 API |
| 지우 | 리서치 · LLM |
| 수현 | 법적 자문 · 인계 운영 |
