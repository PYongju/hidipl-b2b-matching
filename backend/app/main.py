from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from api.v1.routes import router

logger = logging.getLogger(__name__)

app = FastAPI(title="HIDIPL B2B Matching API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(router)


@app.on_event("startup")
async def bootstrap_api_demo_store_on_startup() -> None:
    from services.api_demo.store import store
    from services.api_demo.store_bootstrap import (
        bootstrap_api_demo_store_from_persistence,
    )

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
