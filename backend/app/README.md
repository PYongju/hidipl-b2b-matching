# AI 견적 비교·추천 MVP

## 1. 프로젝트 목적

고객의 견적 요청사항과 파트너사 견적서를 구조화한 뒤, 요구사항과 견적서 간 유사도 및 가격·납기·보증·설치 조건을 기준으로 Top-N 견적서를 추천하는 1차 MVP입니다.

1차 MVP에서는 파트너사 선정/견적 요청/견적 수집 자동화까지 완성하지 않고, 이미 준비된 견적서 목록을 비교·랭킹·설명하는 뒷단 파이프라인을 우선 구현합니다.

---

## 2. 전체 파이프라인

```text
고객 요청 입력
↓
RequirementIngestionPipeline
↓
RequirementInfo + requirement_embedding

견적서 업로드
↓
QuoteIngestionPipeline
↓
PDF/Image: Azure OCR
Excel: Excel 직접 파싱
↓
QuoteDocument + vendor_snapshot + quote_embedding

견적서 비교/랭킹
↓
RecommendationPipeline
↓
Top 3 추천 결과

추천 사유 생성
↓
ExplanationProvider
↓
AI 근거 요약 / 공급사 장단점
```

---

## 3. 실행 방법

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

환경변수 설정 후 테스트를 실행합니다.

```powershell
$env:PYTHONIOENCODING='utf-8'
.env 를 프로젝트 루트에 만들고 실행해도 문제 없습니다.
.venv\Scripts\python.exe -m services.test_api_demo_flow
```

---

## 4. 환경변수 설정 방법

`.env` 파일은 GitHub에 올리지 않습니다.
대신 `.env.example`을 참고해 로컬에서 직접 생성합니다.

```env
# ===========================
# Azure Document Intelligence
# ===========================

DOCUMENTINTELLIGENCE_ENDPOINT=
DOCUMENTINTELLIGENCE_API_KEY=
OCR_PROVIDER=azure
AZURE_DOCUMENT_MODEL_ID=prebuilt-layout

# ===========================
# Azure Open AI Embedding
# ===========================

AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=embedding-3-large
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# ===========================
# Azure Open AI gpt-4.1-mini
# ===========================

AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_CHAT_API_VERSION=2025-01-01-preview
```

---

## 5. 테스트 명령어

```powershell
$env:PYTHONIOENCODING='utf-8' or .env 생성

.venv\Scripts\python.exe -m services.test_requirement_ingestion_pipeline
.venv\Scripts\python.exe -m services.test_quote_ingestion_pipeline
.venv\Scripts\python.exe -m services.test_recommendation_pipeline
.venv\Scripts\python.exe -m services.test_explanation_provider
.venv\Scripts\python.exe -m services.test_api_demo_flow
```

전체 데모 흐름 확인:

```powershell
.venv\Scripts\python.exe -m services.test_full_pipeline_demo
```

---

## 6. API Demo 실행 방법 (테스트용)

API 데모 서버 실행:

```powershell
uvicorn services.api_demo.app:app --reload --port 8000
```

주요 API 흐름:

```text
POST /api/v1/projects
→ 고객 요청 등록

POST /api/v1/projects/{project_id}/quotes
→ 견적서 업로드 및 Quote Pool 생성

POST /api/v1/projects/{project_id}/matches
→ 견적서 Top 3 추천

GET /api/v1/projects/{project_id}/matches
→ 대시보드용 추천 결과 조회

GET /api/v1/projects/{project_id}/matches/{match_id}/explanation
→ AI 추천 사유 조회

POST /api/v1/projects/{project_id}/compare
→ 견적 비교표 생성
```

## TEST 를 위해, 테스트 콘솔용 요약 출력으로 제한되어있음.

## test_api_demo_flow.py 실행 시, config.paths.OUTPUT_DIR 에서 전체 JSON 확인가능

## 7. GitHub에 포함되지 않은 파일 안내

보안 및 용량 문제로 아래 파일은 GitHub에 포함하지 않습니다.

```text
.env
.venv/
__pycache__/
config.paths.OUTPUT_DIR
config.paths.UPLOAD_DIR
config.paths.PARTNER_EMBEDDINGS_PATH
실제 견적서 PDF/XLSX/이미지 파일
Azure Key 또는 비밀정보가 포함된 파일
```

필요한 샘플 견적서는 민감정보를 제거한 익명화 파일만 별도로 추가합니다.

---

## 8. 핵심 구현 모듈

```text
services/requirement/
services/requirement_ingestion/
services/quote_ingestion/
services/parser/
services/embedding/
services/similarity/
services/ranking/
services/recommendation/
services/explanation/
services/api_demo/
```

1차 MVP의 핵심은 `list[QuoteDocument]` 형태의 견적서 풀을 준비한 뒤, 이를 비교·랭킹·설명하는 뒷단 파이프라인을 안정적으로 동작시키는 것입니다.

## 9. 경로의존성 관련 추가사항

프론트/백엔드에서 파일 업로드
↓
UPLOAD_DIR / project_id / filename 으로 저장
↓
저장된 file_path를 QuoteIngestionPipeline에 전달
↓
OCR / Parser / Embedding / Ranking 실행

백엔드 실행 기준 루트는 backend/app 입니다.
공통 경로는 backend/app/config/paths.py에서 관리합니다.

모든 파일 경로는 backend/app/config/paths.py의 공통 Path 상수를 기준으로 정리했습니다.
API에서 업로드 파일을 UPLOAD_DIR에 저장한 뒤, 해당 file_path를 QuoteIngestionPipeline에 전달하면 OCR/Parser/Embedding/Ranking까지 실행됩니다.
서비스 모듈 내부에는 특정 로컬 절대경로나 샘플 파일 경로를 직접 참조하지 않도록 정리했습니다.
