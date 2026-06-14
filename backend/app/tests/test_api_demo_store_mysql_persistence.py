from __future__ import annotations

import os

from services.api_demo.store import ApiDemoStore
from services.api_demo.store_persistence import SqlJsonApiDemoPersistence
from tests.test_api_demo_store_persistence import _populate_store


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
    if not persistence.is_schema_ready():
        print("MySQL persistence tests skipped: schema is not ready")
        return

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

    print("MySQL persistence tests passed")


if __name__ == "__main__":
    main()
