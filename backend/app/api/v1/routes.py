import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import get_db
from services.api_demo import routers as demo_routers
from services.api_demo.schemas import (
    CandidateVendorRequest,
    CandidateVendorsRequest,
    CompareRequest,
    InternalNoteRequest,
    MatchRunRequest,
    ProjectCreateRequest as DemoProjectCreateRequest,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


class ProjectCreateRequest(BaseModel):
    company_name: str
    location: str | None = None
    deadline: str | None = None
    request_text: str


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
            text(
                """
                INSERT INTO projects (
                    project_id, created_at, status, company_name, location, deadline, request_text
                ) VALUES (
                    :project_id, :created_at, :status, :company_name, :location, :deadline, :request_text
                )
                """
            ),
            {
                "project_id": result["project_id"],
                "created_at": datetime.now(),
                "status": "created",
                "company_name": body.company_name,
                "location": body.location,
                "deadline": body.deadline,
                "request_text": body.request_text,
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
    except Exception as e:
        db.rollback()
        logger.warning("projects DB insert failed; returning project result anyway: %s", e)

    return {"ok": True, "data": result, "error": None}


@router.post("/projects/{project_id}/quotes")
async def upload_quotes(project_id: str, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        saved_paths = []
        max_file_size = 100 * 1024 * 1024

        for upload in files:
            content = await upload.read()
            if len(content) > max_file_size:
                raise HTTPException(status_code=413, detail=f"File {upload.filename}: file size limit exceeded")
            await upload.seek(0)

            dest = tmp_dir / Path(upload.filename).name
            with dest.open("wb") as out:
                shutil.copyfileobj(upload.file, out)
            saved_paths.append(dest)

        result = demo_routers.upload_quote_paths(project_id, saved_paths)

        try:
            for quote in result.get("quotes", []):
                db.execute(
                    text(
                        """
                        INSERT INTO quotes (
                            quote_id, project_id, vendor_name, vendor_id,
                            total_supply_price, total_with_vat,
                            delivery_weeks, delivery_basis_raw,
                            warranty_months, created_at
                        ) VALUES (
                            :quote_id, :project_id, :vendor_name, :vendor_id,
                            :total_supply_price, :total_with_vat,
                            :delivery_weeks, :delivery_basis_raw,
                            :warranty_months, :created_at
                        )
                        """
                    ),
                    {
                        "quote_id": quote["quote_id"],
                        "project_id": project_id,
                        "vendor_name": quote.get("vendor_name") or quote.get("vendor_snapshot", {}).get("vendor_name"),
                        "vendor_id": quote.get("vendor_snapshot", {}).get("vendor_id"),
                        "total_supply_price": quote.get("total_supply_price"),
                        "total_with_vat": quote.get("total_with_vat"),
                        "delivery_weeks": quote.get("delivery_weeks"),
                        "delivery_basis_raw": quote.get("delivery_basis_raw"),
                        "warranty_months": quote.get("warranty_months"),
                        "created_at": datetime.now(),
                    },
                )
            db.commit()
        except IntegrityError:
            db.rollback()
        except Exception as e:
            db.rollback()
            logger.warning("quotes DB insert failed; returning upload result anyway: %s", e)

        try:
            db.execute(
                text("UPDATE projects SET status = 'quote_uploaded' WHERE project_id = :project_id"),
                {"project_id": project_id},
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning("project status update failed after quote upload: %s", e)

        return {"ok": True, "data": result, "error": None}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post("/projects/{project_id}/candidate-vendors")
async def get_candidate_vendors(project_id: str, body: CandidateVendorRequest, db: Session = Depends(get_db)):
    try:
        payload = CandidateVendorsRequest(top_n=body.quote_top_n)
        result = demo_routers.run_candidate_vendors(project_id, payload)

        try:
            db.execute(
                text("UPDATE projects SET status = 'partner_matched' WHERE project_id = :project_id"),
                {"project_id": project_id},
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning("project status update failed after candidate-vendors: %s", e)

        return result.get("data", result)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
                {"match_id": match_id, "project_id": project_id, "created_at": datetime.now()},
            )
            for item in result.get("recommendation", {}).get("items", []):
                db.execute(
                    text(
                        """
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
                        """
                    ),
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
                        "matched_rules": str(item.get("matched_rules", [])),
                        "filter_reasons": str(item.get("filter_reasons", [])),
                        "check_required": str(item.get("check_required", [])),
                        "rule_warnings": str(item.get("rule_warnings", [])),
                    },
                )
            db.commit()
        except IntegrityError:
            db.rollback()
        except Exception as e:
            db.rollback()
            logger.warning("match DB insert failed; returning match result anyway: %s", e)

        try:
            db.execute(
                text("UPDATE projects SET status = 'matched' WHERE project_id = :project_id"),
                {"project_id": project_id},
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning("project status update failed after match: %s", e)

        return {"ok": True, "data": result, "error": None}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project(project_id: str, db: Session = Depends(get_db)):
    try:
        row = db.execute(
            text(
                """
                SELECT project_id, status, company_name, location, deadline, request_text, created_at
                FROM projects
                WHERE project_id = :project_id
                """
            ),
            {"project_id": project_id},
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Project not found")
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


@router.get("/projects/{project_id}/matches")
async def get_matches(project_id: str):
    try:
        result = demo_routers.get_matches(project_id)
        return {"ok": True, "data": result, "error": None}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/projects/{project_id}/matches/{match_id}/explanation")
async def get_explanation(project_id: str, match_id: str):
    try:
        result = demo_routers.get_explanation(project_id, match_id)
        return {"ok": True, "data": result, "error": None}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


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


@router.patch("/projects/{project_id}/internal-notes")
async def save_internal_notes(project_id: str, body: InternalNoteRequest, db: Session = Depends(get_db)):
    try:
        if body.notes:
            notes = body.notes
        elif body.screen:
            notes = {body.screen: body.note}
        else:
            raise HTTPException(status_code=400, detail="Invalid request")

        db.execute(
            text("UPDATE projects SET internal_notes = :notes WHERE project_id = :project_id"),
            {"notes": str(notes), "project_id": project_id},
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
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
