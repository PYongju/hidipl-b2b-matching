from __future__ import annotations

from typing import Any

from services.api_demo.store import ApiDemoStore


def bootstrap_api_demo_store_from_persistence(
    store: ApiDemoStore,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    persistence = getattr(store, "persistence", None)
    result: dict[str, Any] = {
        "enabled": bool(persistence),
        "persistence": type(persistence).__name__ if persistence else None,
        "loaded_projects": 0,
        "loaded_projects_with_requirement_result": 0,
        "lazy_hydration_projects": 0,
        "loaded_quote_pools": 0,
        "loaded_matches": 0,
        "loaded_candidate_vendors": 0,
        "azure_calls": 0,
        "warnings": [],
    }
    if persistence is None:
        result["warnings"].append("persistence is not configured; bootstrap skipped")
        return result

    for project in persistence.load_recent_project_records(limit=limit):
        store.restore_project_record(project)
        result["loaded_projects"] += 1
        if getattr(project, "requirement_result", None) is None:
            result["lazy_hydration_projects"] += 1
        else:
            result["loaded_projects_with_requirement_result"] += 1

    for quote_pool in persistence.load_recent_quote_pool_records(limit=limit):
        store.restore_quote_pool_record(quote_pool)
        result["loaded_quote_pools"] += 1

    for match in persistence.load_recent_match_records(limit=limit):
        store.restore_match_record(match)
        result["loaded_matches"] += 1

    for candidate_vendors in persistence.load_recent_candidate_vendor_records(limit=limit):
        store.restore_candidate_vendor_record(candidate_vendors)
        result["loaded_candidate_vendors"] += 1

    result["lazy_hydration_projects"] = len(store.lazy_hydration_project_ids)
    return result
