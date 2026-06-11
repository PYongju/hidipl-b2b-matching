import json
import tempfile
import logging
import shutil
from pathlib import Path
from unittest import result
from services.api_demo import routers as demo_routers

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from pydantic import BaseModel
from services.api_demo.schemas import (
    ProjectCreateRequest as DemoProjectCreateRequest,
    MatchRunRequest, CandidateVendorRequest, CandidateVendorsRequest, InternalNoteRequest,
)
from services.api_demo.schemas import CompareRequest
from sqlalchemy.orm import Session
from fastapi import Depends
from datetime import datetime
from core.database import get_db
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

class ProjectCreateRequest(BaseModel):
    company_name: str
    location: str | None = None
    deadline: str | None = None
    request_text: str

# [P1] 프로젝트 등록
@router.post("/projects")
async def create_project(body: ProjectCreateRequest, db: Session = Depends(get_db)):
    result = demo_routers.create_project(
        DemoProjectCreateRequest(
            company_name=body.company_name,
            location=body.location,
            deadline=body.deadline,
            request_text=body.request_text,
        )
    )
    try:
        db.execute(
            text("INSERT INTO projects (project_id, created_at, status, company_name, location, deadline, request_text) VALUES (:project_id, :created_at, :status, :company_name, :location, :deadline, :request_text)"),
            {
                "project_id": result["project_id"],
                "created_at": datetime.now(),
                "status": "created",
                "company_name": body.company_name,
                "location": body.location,
                "deadline": body.deadline,
                "request_text": body.request_text,
            }
        )
        db.commit()
    except IntegrityError:
        db.rollback()
    except Exception as e:
        db.rollback()
        logger.warning("projects DB insert 실패 (비치명적): %s", e)

    return {"ok": True, "data": result, "error": None}


# [P2] 견적서 업로드 + OCR + Canonical 변환
@router.post("/projects/{project_id}/quotes")
async def upload_quotes(project_id: str, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        saved_paths = []
        MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
        for f in files:
            content = await f.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail=f"File {f.filename}: 파일 크기 초과 (최대 100MB)")
            await f.seek(0)  # 파일 포인터를 처음으로 되돌림

            dest = tmp_dir / Path(f.filename).name
            with dest.open("wb") as out:
                shutil.copyfileobj(f.file, out)
            saved_paths.append(dest)

        result = demo_routers.upload_quote_paths(project_id, saved_paths)
        try:
            for quote in result.get("quotes", []):
                db.execute(
                    text("""
                        INSERT INTO quotes (
                            quote_id, project_id, vendor_name, vendor_id,
                            project_name, received_at,
                            total_supply_price, total_with_vat,
                            delivery_weeks, delivery_basis_raw,
                            warranty_months, created_at
                        ) VALUES (
                            :quote_id, :project_id, :vendor_name, :vendor_id,
                            :project_name, :received_at,
                            :total_supply_price, :total_with_vat,
                            :delivery_weeks, :delivery_basis_raw,
                            :warranty_months, :created_at
                        )
                    """),
                    {
                        "quote_id": quote["quote_id"],
                        "project_id": project_id,
                        "vendor_name": quote["vendor_name"],
                        "vendor_id": (quote.get("vendor_snapshot") or {}).get("vendor_id"),
                        "project_name": quote.get("project_name") or "미입력",
                        "received_at": quote.get("received_at") or datetime.now(),
                        "total_supply_price": quote["total_supply_price"],
                        "total_with_vat": quote.get("total_with_vat"),
                        "delivery_weeks": quote.get("delivery_weeks"),
                        "delivery_basis_raw": quote.get("delivery_basis_raw"),
                        "warranty_months": quote.get("warranty_months"),
                        "created_at": datetime.now(),
                    }
                )
            db.commit()
        except IntegrityError:
            db.rollback()
        except Exception as e:
            db.rollback()
            raise  # 또는 로깅 후 HTTP 500 반환
        db.execute(
            text("UPDATE projects SET status = 'quote_uploaded' WHERE project_id = :project_id"),
            {"project_id": project_id}
        )
        db.commit()
        return {"ok": True, "data": result, "error": None}

    except KeyError as e:
        raise HTTPException(status_code=404, detail="잘못된 요청입니다.")
    except ValueError as e:
        raise HTTPException(status_code=422, detail="잘못된 요청입니다.")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

#[P2-1] 파트너 후보 추천
@router.post("/projects/{project_id}/candidate-vendors")
async def get_candidate_vendors(project_id: str, body: CandidateVendorRequest, db: Session = Depends(get_db)):
    try:
        payload = CandidateVendorsRequest(top_n=body.quote_top_n)
        result = demo_routers.run_candidate_vendors(project_id, payload)
        db.execute(
            text("UPDATE projects SET status = 'partner_matched' WHERE project_id = :project_id"),
            {"project_id": project_id}
        )
        db.commit()
        return result.get("data", result)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="잘못된 요청입니다.")


# [P3] 매칭 실행
@router.post("/projects/{project_id}/matches")
async def run_matching(project_id: str, body: MatchRunRequest, db: Session = Depends(get_db)):
    try:
        result = demo_routers.run_match(
            project_id,
            MatchRunRequest(
                quote_top_n=body.quote_top_n or 3,
                run_explanation=body.run_explanation or False,
                explanation_provider=body.explanation_provider or None,
            ),
        )
        try:
            match_id = result["match_id"]
            db.execute(
                text("INSERT INTO match_results (match_id, project_id, created_at) VALUES (:match_id, :project_id, :created_at)"),
                {"match_id": match_id, "project_id": project_id, "created_at": datetime.now()}
            )
            for item in result.get("recommendation", {}).get("items", []):
                db.execute(
                    text("""
                        INSERT INTO match_result_items (
                            match_id, quote_id, rank, final_score,
                            spec_score, price_score, delivery_score,
                            warranty_score, installation_score,
                            matched_rules, filter_reasons, check_required, rule_warnings
                        ) VALUES (
                            :match_id, :quote_id, :rank, :final_score,
                            :spec_score, :price_score, :delivery_score,
                            :warranty_score, :installation_score,
                            :matched_rules, :filter_reasons, :check_required, :rule_warnings
                        )
                    """),
                    {
                        "match_id": match_id,
                        "quote_id": item["quote_id"],
                        "rank": item["rank"],
                        "final_score": item.get("final_score", 0.0),
                        "spec_score": item.get("spec_score", 0.0),
                        "price_score": item.get("price_score", 0.0),
                        "delivery_score": item.get("delivery_score", 0.0),
                        "warranty_score": item.get("warranty_score", 0.0),
                        "installation_score": item.get("installation_score", 0.0),
                        "matched_rules": json.dumps(item.get("matched_rules") or [], ensure_ascii=False),
                        "filter_reasons": json.dumps(item.get("filter_reasons") or [], ensure_ascii=False),
                        "check_required": json.dumps(item.get("check_required") or [], ensure_ascii=False),
                        "rule_warnings": json.dumps(item.get("rule_warnings") or [], ensure_ascii=False),
                    }
                )
            db.commit()
        except IntegrityError:
            db.rollback()
        except Exception as e:
            db.rollback()
            raise  # 또는 로깅 후 HTTP 500 반환

        db.execute(
            text("UPDATE projects SET status = 'matched' WHERE project_id = :project_id"),
            {"project_id": project_id}
        )
        db.commit()
        return {"ok": True, "data": result, "error": None}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# [P8] 프로젝트 상태 조회
@router.get("/projects/{project_id}")
async def get_project(project_id: str, db: Session = Depends(get_db)):
    try:
        row = db.execute(
            text("SELECT project_id, status, company_name, location, deadline, request_text, created_at FROM projects WHERE project_id = :project_id"),
            {"project_id": project_id}
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
        return {
            "ok": True,
            "data": {
                "project_id": row.project_id,
                "status": row.status,
                "company_name": row.company_name,
                "location": row.location,
                "deadline": row.deadline,
                "request_text": row.request_text,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            },
            "error": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [P4] 매칭 결과 조회 (대시보드용)
@router.get("/projects/{project_id}/matches")
async def get_matches(project_id: str):
    try:
        result = demo_routers.get_matches(project_id)
        return {"ok": True, "data": result, "error": None}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# [P5] LLM 근거 생성 결과
@router.get("/projects/{project_id}/matches/{match_id}/explanation")
async def get_explanation(project_id: str, match_id: str):
    try:
        result = demo_routers.get_explanation(project_id, match_id)
        return {"ok": True, "data": result, "error": None}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

# [P6] 견적 비교표 생성 (FR-2)
# status는 백엔드가 CellStatus enum으로 계산해 내려준다.
# 프론트는 status -> 라벨 매핑만 담당한다.
# rows 배열은 rank 순 고정
@router.post("/projects/{project_id}/compare")
async def compare_quotes(project_id: str, body: CompareRequest):
    try:
        result = demo_routers.compare_quotes(
            project_id,
            CompareRequest(
                quote_ids=body.quote_ids,
                top_n=body.top_n,
            ),
        )
        return {"ok": True, "data": result, "error": None}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
# [P7] 내부 메모 저장
@router.patch("/projects/{project_id}/internal-notes")
async def save_internal_notes(project_id: str, body: InternalNoteRequest, db: Session = Depends(get_db)):
    try:
        if body.notes:
            notes = body.notes
        elif body.screen:
            notes = {body.screen: body.note}
        else:
            raise HTTPException(status_code=400, detail="잘못된 요청입니다.")
        db.execute(
            text("UPDATE projects SET internal_notes = :notes WHERE project_id = :project_id"),
            {
                "notes": str(notes),
                "project_id": project_id,
            }
        )
        db.commit()
        return {
            "ok": True,
            "data": {
                "project_id": project_id,
                "notes": notes,
                "updated_at": datetime.now().isoformat(),
            },
            "error": None,
        }
    except Exception as e:
        db.rollback()
        raise
