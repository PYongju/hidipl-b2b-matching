try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
except ImportError:
    FastAPI = None
    File = None
    HTTPException = Exception
    UploadFile = None

from pathlib import Path

from services.api_demo.routers import (
    compare_quotes,
    create_project,
    get_explanation,
    get_matches,
    run_candidate_vendors,
    run_match,
    upload_quote_paths,
)
from services.api_demo.schemas import CompareRequest, MatchRunRequest, ProjectCreateRequest


if FastAPI is not None:
    app = FastAPI(title="Quote Recommendation API Demo", version="0.1.0")

    @app.post("/api/v1/projects")
    def post_project(payload: ProjectCreateRequest):
        try:
            return create_project(payload)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/v1/projects/{project_id}/quotes")
    async def post_quotes(project_id: str, files: list[UploadFile] = File(...)):
        upload_dir = Path("data/api_demo_uploads") / project_id
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
    def post_candidate_vendors(project_id: str, top_n: int = 10):
        try:
            return run_candidate_vendors(project_id, top_n=top_n)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
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
