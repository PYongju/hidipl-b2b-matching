from fastapi import APIRouter, UploadFile, File
from typing import Optional

router = APIRouter(prefix="/api/v1")


# [P1] 프로젝트 등록
@router.post("/projects")
async def create_project(body: dict):
    return {
        "ok": True,
        "data": {
            "project_id": "P-20260529-001",
            "created_at": "2026-05-29T10:00:00+09:00",
        },
        "error": None,
    }


# [P2] 견적서 업로드 + OCR + Canonical 변환
@router.post("/projects/{project_id}/quotes")
async def upload_quotes(project_id: str, files: list[UploadFile] = File(...)):
    return {
        "ok": True,
        "data": {
            "uploaded_count": len(files),
            "quotes": [],              # azure_ocr_to_canonical() 완성 후 채움 (5/30)
        },
        "error": None,
    }


# [P3] 매칭 실행
@router.post("/projects/{project_id}/matches")
async def run_matching(project_id: str, body: dict):
    return {
        "ok": True,
        "data": {
            "match_id": "M-20260529-001",
            "project_id": project_id,
            "results": [],             # score.rank() 연결 후 채움
            "excluded": [],
        },
        "error": None,
    }


# [P4] 매칭 결과 조회 (대시보드용)
@router.get("/projects/{project_id}/matches")
async def get_matches(project_id: str, match_id: Optional[str] = None):
    return {
        "ok": True,
        "data": {
            "match_id": match_id or "M-20260529-001",
            "project_id": project_id,
            "results": [],
            "excluded": [],
        },
        "error": None,
    }


# [P5] LLM 근거 생성 결과
@router.get("/projects/{project_id}/matches/{match_id}/explanation")
async def get_explanation(project_id: str, match_id: str):
    return {
        "ok": True,
        "data": {
            "match_id": match_id,
            "explanations": [],        # explain.generate() 연결 후 채움
        },
        "error": None,
    }


# [P6] 견적 비교표 생성 (FR-2)
# delivery_basis_raw == '별도협의' 시 프론트에서 "출장비 별도" 배지 처리
# check_required null 항목은 프론트에서 "확인 필요" 배지 처리
# rows 배열은 rank 순 고정
@router.post("/projects/{project_id}/compare")
async def compare_quotes(project_id: str, body: dict):
    return {
        "ok": True,
        "data": {
        "rows": [],   # build_compare_response() 연동 후 채움
        },
        "error": None,
    }