import json
import tempfile
import logging
import shutil
from pathlib import Path
from unittest import result
from services.api_demo import routers as demo_routers
from services.api_demo.store import store as demo_store

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
    company_name: str = ""
    location: str | None = None
    deadline: str | None = None
    request_text: str = ""

# [P1] 프로젝트 등록
@router.post("/projects")
async def create_project(body: ProjectCreateRequest, db: Session = Depends(get_db)):
    try:
        result = demo_routers.create_project(
            DemoProjectCreateRequest(
                company_name=body.company_name,
                location=body.location,
                deadline=body.deadline,
                request_text=body.request_text,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        db.execute(
            text("""
                INSERT INTO projects (
                    project_id, created_at, status, company_name, location, deadline, request_text
                ) VALUES (
                    :project_id, :created_at, :status, :company_name, :location, :deadline, :request_text
                )
                ON DUPLICATE KEY UPDATE
                    company_name = VALUES(company_name),
                    location = VALUES(location),
                    deadline = VALUES(deadline),
                    request_text = VALUES(request_text)
            """),
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
                        ON DUPLICATE KEY UPDATE
                            vendor_name = VALUES(vendor_name),
                            vendor_id = VALUES(vendor_id),
                            project_name = VALUES(project_name),
                            total_supply_price = VALUES(total_supply_price),
                            total_with_vat = VALUES(total_with_vat),
                            delivery_weeks = VALUES(delivery_weeks),
                            delivery_basis_raw = VALUES(delivery_basis_raw),
                            warranty_months = VALUES(warranty_months)
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
            text("UPDATE projects SET status = 'partner_matched' WHERE project_id = :project_id AND status = 'partner_matching'"),
            {"project_id": project_id}
        )
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

# [P2-1-GET] 파트너 후보 추천 결과 조회
@router.get("/projects/{project_id}/candidate-vendors")
async def get_candidate_vendors_result(project_id: str):
    try:
        result = demo_routers.get_candidate_vendors(project_id)
        if not result:
            raise HTTPException(status_code=404, detail="후보 공급사 데이터가 없습니다.")
        return {"ok": True, "data": result, "error": None}
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")

#[P2-1] 파트너 후보 추천
@router.post("/projects/{project_id}/candidate-vendors")
async def get_candidate_vendors(project_id: str, body: CandidateVendorRequest, db: Session = Depends(get_db)):
    try:
        payload = CandidateVendorsRequest(top_n=body.quote_top_n)
        result = demo_routers.run_candidate_vendors(project_id, payload)
        db.execute(
            text("UPDATE projects SET status = 'partner_matching' WHERE project_id = :project_id"),
            {"project_id": project_id}
        )
        db.commit()
        return result.get("data", result)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="잘못된 요청입니다.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
                text("""
                    INSERT INTO match_results (match_id, project_id, created_at)
                    VALUES (:match_id, :project_id, :created_at)
                    ON DUPLICATE KEY UPDATE
                        project_id = VALUES(project_id)
                """),
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
                        ON DUPLICATE KEY UPDATE
                            quote_id = VALUES(quote_id),
                            final_score = VALUES(final_score),
                            spec_score = VALUES(spec_score),
                            price_score = VALUES(price_score),
                            delivery_score = VALUES(delivery_score),
                            warranty_score = VALUES(warranty_score),
                            installation_score = VALUES(installation_score),
                            matched_rules = VALUES(matched_rules),
                            filter_reasons = VALUES(filter_reasons),
                            check_required = VALUES(check_required),
                            rule_warnings = VALUES(rule_warnings)
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


# [P4] 매칭 결과 조회 (대시보드용)
@router.get("/projects/{project_id}/matches")
async def get_matches(project_id: str, product_group: str | None = None):
    try:
        result = demo_routers.get_matches(project_id, product_group=product_group)
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
async def compare_quotes(
    project_id: str,
    body: CompareRequest,
    product_group: str | None = None,
):
    try:
        result = demo_routers.compare_quotes(
            project_id,
            CompareRequest(
                quote_ids=body.quote_ids,
                top_n=body.top_n,
            ),
            product_group=product_group,
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

# [P9] 프로젝트 목록 조회
@router.get("/projects")
async def list_projects(db: Session = Depends(get_db)):
    try:
        rows = db.execute(
            text("SELECT project_id, status, workflow_status, company_name, location, deadline, request_text, created_at FROM projects ORDER BY created_at DESC")
        ).fetchall()
        return {
            "ok": True,
            "data": [
                {
                    "project_id": row.project_id,
                    "status": row.status,
                    "workflow_status": row.workflow_status,
                    "company_name": row.company_name,
                    "location": row.location,
                    "deadline": row.deadline,
                    "request_text": row.request_text,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
            "error": None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# [P10] 프로젝트 삭제 (선택/전체)
class ProjectDeleteRequest(BaseModel):
    project_ids: List[str]

@router.delete("/projects")
async def delete_projects(body: ProjectDeleteRequest, db: Session = Depends(get_db)):
    try:
        if not body.project_ids:
            raise HTTPException(status_code=400, detail="project_ids가 비어 있습니다.")
        for pid in body.project_ids:
            db.execute(
                text("DELETE FROM projects WHERE project_id = :project_id"),
                {"project_id": pid}
            )
        db.commit()
        return {"ok": True, "data": {"deleted_count": len(body.project_ids)}, "error": None}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
# [P11] 프로젝트 정보 수정 (자동 임시저장)
class ProjectUpdateRequest(BaseModel):
    company_name: str | None = None
    location: str | None = None
    deadline: str | None = None
    request_text: str | None = None
    workflow_status: str | None = None
    requested_vendor_ids: list[str] | None = None

@router.patch("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdateRequest, db: Session = Depends(get_db)):
    try:
        requested_vendor_ids_for_cache = None
        row = db.execute(
            text("SELECT project_id FROM projects WHERE project_id = :project_id"),
            {"project_id": project_id}
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
        db.execute(
            text("""
                UPDATE projects SET
                    company_name = COALESCE(:company_name, company_name),
                    location = COALESCE(:location, location),
                    deadline = COALESCE(:deadline, deadline),
                    request_text = COALESCE(:request_text, request_text),
                    workflow_status = COALESCE(:workflow_status, workflow_status)
                WHERE project_id = :project_id
            """),
            {
                "company_name": body.company_name,
                "location": body.location,
                "deadline": body.deadline,
                "request_text": body.request_text,
                "workflow_status": body.workflow_status,
                "project_id": project_id,
            }
        )

        if body.requested_vendor_ids is not None:
            cv_row = db.execute(
                text(
                    "SELECT candidate_vendor_id FROM candidate_vendors "
                    "WHERE project_id = :project_id ORDER BY created_at DESC LIMIT 1"
                ),
                {"project_id": project_id},
            ).fetchone()
            if cv_row:
                db.execute(
                    text(
                        "UPDATE candidate_vendors SET requested_vendor_ids_json = :ids "
                        "WHERE candidate_vendor_id = :candidate_vendor_id"
                    ),
                    {
                        "ids": json.dumps(body.requested_vendor_ids, ensure_ascii=False),
                        "candidate_vendor_id": cv_row.candidate_vendor_id,
                    },
                )
                requested_vendor_ids_for_cache = body.requested_vendor_ids

        db.commit()
        if requested_vendor_ids_for_cache is not None:
            try:
                updated_memory = demo_store.update_candidate_vendor_requested_vendor_ids(
                    project_id=project_id,
                    requested_vendor_ids=requested_vendor_ids_for_cache,
                )
                if not updated_memory:
                    logger.info(
                        "candidate vendor record not in memory; "
                        "requested_vendor_ids updated in DB only. project_id=%s count=%s",
                        project_id,
                        len(requested_vendor_ids_for_cache),
                    )
            except Exception:
                logger.warning(
                    "failed to update in-memory requested_vendor_ids cache. project_id=%s",
                    project_id,
                    exc_info=True,
                )

        return {
            "ok": True,
            "data": {
                "project_id": project_id,
                "updated_at": datetime.now().isoformat(),
            },
            "error": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
# [P12] 후보 공급사 미기재 필드 수정
class CandidateVendorUpdateRequest(BaseModel):
    response_speed: str | None = None
    financial_status: str | None = None
    company_location: str | None = None
    installation_count: int | None = None
    special_notes: str | list[str] | None = None

@router.patch("/projects/{project_id}/candidate-vendors/{vendor_name}")
async def update_candidate_vendor(
    project_id: str,
    vendor_name: str,
    body: CandidateVendorUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                "SELECT candidate_vendor_id, candidate_vendor_result_json "
                "FROM candidate_vendors WHERE project_id = :project_id "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"project_id": project_id},
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="후보 공급사 데이터가 없습니다.")

        result_json = json.loads(row.candidate_vendor_result_json)

        update_fields = body.model_dump(exclude_none=True)
        if not update_fields:
            raise HTTPException(status_code=400, detail="수정할 필드가 없습니다.")

        if "special_notes" in update_fields:
            update_fields["special_notes"] = _normalize_special_notes(
                update_fields["special_notes"]
            )

        matched = _update_candidate_vendor_result_json(
            result_json,
            vendor_name=vendor_name,
            update_fields=update_fields,
        )
        if not matched:
            raise HTTPException(status_code=404, detail=f"'{vendor_name}' 공급사를 찾을 수 없습니다.")

        db.execute(
            text(
                "UPDATE candidate_vendors SET candidate_vendor_result_json = :result_json "
                "WHERE candidate_vendor_id = :candidate_vendor_id"
            ),
            {
                "result_json": json.dumps(result_json, ensure_ascii=False),
                "candidate_vendor_id": row.candidate_vendor_id,
            },
        )
        db.commit()

        demo_store.update_candidate_vendor_fields(project_id, vendor_name, update_fields)

        return {
            "ok": True,
            "data": {
                "project_id": project_id,
                "vendor_name": vendor_name,
                "updated_fields": update_fields,
            },
            "error": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def _update_candidate_vendor_result_json(
    result_json: dict,
    *,
    vendor_name: str,
    update_fields: dict,
) -> bool:
    matched = False
    seen_ids = set()
    for list_name in [
        "all_candidates",
        "candidates",
        "selected_candidates",
        "filtered_candidates",
        "candidate_vendors",
    ]:
        candidates = result_json.get(list_name)
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            candidate_id = id(candidate)
            if candidate_id in seen_ids:
                continue
            seen_ids.add(candidate_id)

            metadata = candidate.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            if (
                candidate.get("partner_name") != vendor_name
                and candidate.get("vendor_name") != vendor_name
                and metadata.get("partner_name") != vendor_name
                and metadata.get("vendor_name") != vendor_name
            ):
                continue

            matched = True
            for key, value in update_fields.items():
                if key == "special_notes":
                    metadata = candidate.setdefault("metadata", {})
                    if not isinstance(metadata, dict):
                        metadata = {}
                        candidate["metadata"] = metadata
                    metadata["special_notes"] = value
                    metadata.setdefault("manual_update", {})["special_notes"] = value
                    continue
                candidate[key] = value
    return matched


def _normalize_special_notes(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]
    text = str(value).strip()
    return [text] if text else []


# [P13] 제품군별 견적 확정
class ConfirmSelectionRequest(BaseModel):
    product_group: str
    selected_quote_ids: list[str]

@router.post("/projects/{project_id}/confirm")
async def confirm_selection(project_id: str, body: ConfirmSelectionRequest):
    try:
        from services.api_demo.demo_state import demo_confirm_state
        record = demo_confirm_state.confirm(
            project_id=project_id,
            product_group=body.product_group,
            selected_quote_ids=body.selected_quote_ids,
        )
        return {
            "ok": True,
            "data": {
                "project_id": record.project_id,
                "product_group": record.product_group,
                "selected_quote_ids": record.selected_quote_ids,
                "confirmed_at": record.confirmed_at,
            },
            "error": None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [P8] 프로젝트 상태 조회
@router.get("/projects/{project_id}")
async def get_project(project_id: str, db: Session = Depends(get_db)):
    try:
        row = db.execute(
            text("SELECT project_id, status, workflow_status, company_name, location, deadline, request_text, created_at FROM projects WHERE project_id = :project_id"),
            {"project_id": project_id}
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
        return {
            "ok": True,
            "data": {
                "project_id": row.project_id,
                "status": row.status,
                "workflow_status": row.workflow_status,
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
    
