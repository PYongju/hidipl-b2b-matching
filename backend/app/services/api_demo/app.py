try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
except ImportError:
    FastAPI = None
    File = None
    HTTPException = Exception
    UploadFile = None

from typing import Any
import logging
import os

from config.paths import UPLOAD_DIR
from services.api_demo.routers import (
    compare_quotes,
    create_project,
    get_candidate_vendors,
    get_explanation,
    get_matches,
    run_candidate_vendors,
    run_match,
    upload_quote_paths,
)
from services.api_demo.schemas import (
    CandidateVendorRequest,
    CandidateVendorsRequest,
    CompareRequest,
    MatchRunRequest,
    ProjectCreateRequest,
)


logger = logging.getLogger(__name__)


def coerce_candidate_vendors_payload(payload: Any) -> CandidateVendorsRequest | None:
    if payload is None:
        return None
    if isinstance(payload, CandidateVendorsRequest):
        return payload
    if isinstance(payload, CandidateVendorRequest):
        return CandidateVendorsRequest(top_n=payload.quote_top_n)
    if isinstance(payload, dict):
        data = dict(payload)
        if "quote_top_n" in data and "top_n" not in data:
            data["top_n"] = data["quote_top_n"]
        return CandidateVendorsRequest(**data)
    raise TypeError(
        "candidate-vendors route expected CandidateVendorsRequest, "
        f"CandidateVendorRequest, dict, or None, got {type(payload).__name__}"
    )


if FastAPI is not None:
    app = FastAPI(title="Quote Recommendation API Demo", version="0.1.0")

    @app.on_event("startup")
    async def bootstrap_api_demo_store_on_startup() -> None:
        from services.api_demo.store import store
        from services.api_demo.store_bootstrap import bootstrap_api_demo_store_from_persistence

        if not getattr(store, "persistence", None):
            return
        enabled = os.getenv("API_DEMO_STORE_BOOTSTRAP_ON_STARTUP", "true").strip().lower()
        if enabled in {"0", "false", "no", "off"}:
            return
        limit_text = os.getenv("API_DEMO_STORE_BOOTSTRAP_LIMIT", "").strip()
        limit = int(limit_text) if limit_text.isdigit() else None
        result = bootstrap_api_demo_store_from_persistence(store, limit=limit)
        logger.info(
            "API demo store bootstrap complete: persistence=%s loaded_projects=%s "
            "lazy_hydration_projects=%s loaded_quote_pools=%s loaded_matches=%s "
            "loaded_candidate_vendors=%s azure_calls=%s",
            result.get("persistence"),
            result.get("loaded_projects"),
            result.get("lazy_hydration_projects"),
            result.get("loaded_quote_pools"),
            result.get("loaded_matches"),
            result.get("loaded_candidate_vendors"),
            result.get("azure_calls"),
        )

    @app.post("/api/v1/projects")
    def post_project(payload: ProjectCreateRequest):
        try:
            return create_project(payload)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/v1/projects/{project_id}/quotes")
    async def post_quotes(project_id: str, files: list[UploadFile] = File(...)):
        upload_dir = UPLOAD_DIR / project_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for file in files:
            path = upload_dir / file.filename
            path.write_bytes(await file.read())
            paths.append(path)
        try:
            return upload_quote_paths(project_id, paths)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/v1/projects/{project_id}/matches")
    def post_matches(project_id: str, payload: MatchRunRequest):
        try:
            return run_match(project_id, payload)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/v1/projects/{project_id}/matches")
    def get_project_matches(project_id: str):
        try:
            return get_matches(project_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.get("/api/v1/projects/{project_id}/matches/{match_id}/explanation")
    def get_match_explanation(project_id: str, match_id: str):
        try:
            return get_explanation(project_id, match_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/api/v1/projects/{project_id}/compare")
    def post_compare(project_id: str, payload: CompareRequest):
        try:
            return compare_quotes(project_id, payload)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/v1/projects/{project_id}/candidate-vendors")
    def post_candidate_vendors(
        project_id: str,
        payload: dict[str, Any] | None = None,
    ):
        try:
            candidate_payload = coerce_candidate_vendors_payload(payload)
            return run_candidate_vendors(project_id, payload=candidate_payload)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/v1/projects/{project_id}/candidate-vendors")
    def get_project_candidate_vendors(project_id: str):
        try:
            response = get_candidate_vendors(project_id)
            if not response.get("ok"):
                raise HTTPException(status_code=404, detail=response.get("error"))
            return response
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))
else:
    app = None


def main() -> None:
    if FastAPI is None:
        print(
            "FastAPI가 설치되어 있지 않습니다. "
            "API 서버 실행은 `pip install fastapi uvicorn python-multipart` 후 가능합니다. "
            "`python -m services.test_api_demo_flow`로 데모 흐름은 검증할 수 있습니다."
        )
        return

    import uvicorn

    uvicorn.run("services.api_demo.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
