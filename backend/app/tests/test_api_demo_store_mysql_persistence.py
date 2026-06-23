from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional for non-DB tests.
    load_dotenv = None


def _load_app_env() -> None:
    if load_dotenv is None:
        return
    app_dir = Path(__file__).resolve().parents[1]
    env_path = app_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_app_env()

from services.api_demo.store import ApiDemoStore, store
from services.api_demo.store_persistence import SqlJsonApiDemoPersistence
from tests.test_api_demo_store_persistence import _populate_store
from services.explanation.schemas import RecommendationExplanationResult, SupplierExplanation


def main() -> None:
    if os.getenv("RUN_MYSQL_PERSISTENCE_TESTS") != "1":
        print("MySQL persistence tests skipped: RUN_MYSQL_PERSISTENCE_TESTS is not 1")
        return

    required_env = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    missing = [name for name in required_env if not os.getenv(name)]
    if missing:
        print(f"MySQL persistence tests skipped: missing env {missing}")
        return

    persistence = SqlJsonApiDemoPersistence(enabled=True)
    schema_ready = persistence.is_schema_ready()
    print("schema_ready:", schema_ready)
    print("global_store_persistence:", type(getattr(store, "persistence", None)).__name__)
    if not schema_ready:
        print("MySQL persistence tests skipped: schema is not ready")
        return
    assert getattr(store, "persistence", None) is not None
    assert type(store.persistence).__name__ == "SqlJsonApiDemoPersistence"
    assert store.persistence.is_schema_ready() is True

    store1 = ApiDemoStore(persistence=persistence)
    records = _populate_store(store1)
    project_id = records["project"].project_id
    match_id = records["match"].match_id

    store2 = ApiDemoStore(persistence=persistence)
    assert store2.get_project(project_id) is not None
    assert store2.get_quote_pool(project_id) is not None
    assert store2.get_candidate_vendors(project_id) is not None
    assert store2.get_match(project_id, match_id) is not None
    assert store2.get_latest_match(project_id) is not None

    explanation = RecommendationExplanationResult(
        request_id="request_mysql_test",
        customer_name="일강이앤아이",
        overall_summary="MySQL persistence explanation update test",
        supplier_explanations=[
            SupplierExplanation(
                quote_id="quote_001",
                vendor_name="효성ITX",
                rank=1,
                card_summary="저장/조회 검증",
                strengths=[],
                weaknesses=[],
                check_required=[],
            )
        ],
        provider="template",
        warnings=[],
    )
    store2.update_match_explanation(
        project_id=project_id,
        match_id=match_id,
        explanation_result=explanation,
    )
    store3 = ApiDemoStore(persistence=persistence)
    restored_match = store3.get_match(project_id, match_id)
    assert restored_match is not None
    assert restored_match.explanation_result is not None
    assert (
        restored_match.explanation_result.overall_summary
        == "MySQL persistence explanation update test"
    )

    print("MySQL persistence tests passed")


if __name__ == "__main__":
    main()
