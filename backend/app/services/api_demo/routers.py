import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from config.paths import UPLOAD_DIR
from services.api_demo.project_requirement_adapter import (
    build_requirement_info_from_project_payload,
    build_requirement_info_from_project_payload_dict,
    is_frontend_project_payload,
)
from services.api_demo.response_builders import (
    build_candidate_vendors_not_found_response,
    build_candidate_vendors_response,
    build_compare_response,
    build_explanation_response,
    build_grouped_compare_response,
    build_project_response,
    build_quote_upload_response,
    build_recommendation_response,
)
from services.api_demo.schemas import (
    CandidateVendorsRequest,
    CompareRequest,
    MatchRunRequest,
    ProjectCreateRequest,
)
from services.api_demo.store import store
from services.explanation.factory import create_explanation_provider
from services.partner_matching.factory import create_partner_matching_pipeline
from services.quote_ingestion.factory import create_quote_ingestion_pipeline
from services.recommendation.product_group_filter import canonicalize_product_group
from services.recommendation.factory import create_recommendation_pipeline
from services.requirement_ingestion.factory import create_requirement_ingestion_pipeline


SUPPORTED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls"}


def create_project(payload: ProjectCreateRequest) -> dict[str, Any]:
    request_id = f"request_{uuid4().hex[:8]}"
    pipeline = create_requirement_ingestion_pipeline()
    if is_frontend_project_payload(payload):
        requirement_info = build_requirement_info_from_project_payload(
            payload,
            request_id=request_id,
        )
        requirement_result = pipeline.process_requirement_info(
            requirement_info,
            request_id=request_id,
        )
    else:
        requirement_result = pipeline.process_text(
            payload.request_text,
            request_id=request_id,
        )
    record = store.create_project(
        company_name=payload.company_name,
        location=payload.location,
        deadline=payload.deadline,
        request_text=payload.request_text,
        requirement_result=requirement_result,
        original_request_text=payload.request_text,
        requirement_source=requirement_result.metadata.get("requirement_source"),
    )
    return build_project_response(record)


def upload_quote_paths(project_id: str, file_paths: list[Path]) -> dict[str, Any]:
    project = _require_project(project_id)
    upload_dir = UPLOAD_DIR / project_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_paths = []
    failed_files = []
    for path in file_paths:
        path = Path(path)
        if path.suffix.lower() not in SUPPORTED_UPLOAD_EXTENSIONS:
            failed_files.append({"file_path": str(path), "error": "지원하지 않는 확장자"})
            continue
        if not path.exists():
            failed_files.append({"file_path": str(path), "error": "파일 없음"})
            continue

        target = upload_dir / path.name
        if path.resolve() != target.resolve():
            shutil.copy2(path, target)
        stored_paths.append(target)

    pipeline = create_quote_ingestion_pipeline()
    batch_result = pipeline.process_files(
        stored_paths,
        request_id=project.request_id,
    )
    failed_files.extend(batch_result.failed_files)

    if not batch_result.results:
        raise ValueError("처리 성공한 견적서가 없습니다.")

    _attach_candidate_vendor_links(project_id, batch_result.results)

    quote_pool = store.save_quote_pool(
        project_id=project_id,
        uploaded_files=[str(path) for path in stored_paths],
        quote_ingestion_results=batch_result.results,
        failed_files=failed_files,
    )
    return build_quote_upload_response(project_id, quote_pool)


def run_match(project_id: str, payload: MatchRunRequest) -> dict[str, Any]:
    project = _require_project(project_id)
    quote_pool = _require_quote_pool(project_id)
    candidate_vendor_record = store.get_candidate_vendors(project_id)
    selected_vendor_names = (
        list(candidate_vendor_record.selected_vendor_names)
        if candidate_vendor_record is not None
        else None
    )

    pipeline = create_recommendation_pipeline("rule")
    grouped_results = pipeline.recommend_grouped_by_product_group(
        project.requirement_result,
        quote_pool.quote_ingestion_results,
        top_n=payload.quote_top_n,
    )
    recommendation_result = pipeline.combine_grouped_results(
        project.requirement_result,
        grouped_results,
        top_n=payload.quote_top_n,
    )
    recommendation_result.metadata.update(
        {
            "candidate_vendor_matching_executed": candidate_vendor_record is not None,
            "selected_vendor_names": selected_vendor_names or [],
            "requested_vendor_names": (
                list(candidate_vendor_record.requested_vendor_names)
                if candidate_vendor_record is not None
                else []
            ),
            "candidate_vendor_filter_applied": False,
        }
    )
    for result in grouped_results.values():
        result.metadata.update(
            {
                "candidate_vendor_matching_executed": candidate_vendor_record is not None,
                "selected_vendor_names": selected_vendor_names or [],
                "requested_vendor_names": (
                    list(candidate_vendor_record.requested_vendor_names)
                    if candidate_vendor_record is not None
                    else []
                ),
                "candidate_vendor_filter_applied": False,
            }
        )

    explanation_result = None
    grouped_explanations: dict[str, Any] = {}
    if payload.run_explanation:
        explanation_result = _generate_explanation(
            recommendation_result,
            payload.explanation_provider,
        )
        for product_group, group_result in grouped_results.items():
            grouped_explanations[product_group] = _generate_explanation(
                group_result,
                payload.explanation_provider,
            )
        recommendation_result.metadata["product_group_explanations"] = {
            product_group: build_explanation_response(result)
            for product_group, result in grouped_explanations.items()
        }

    match_record = store.save_match(
        project_id=project_id,
        recommendation_result=recommendation_result,
        explanation_result=explanation_result,
    )
    return {
        "project_id": project_id,
        "match_id": match_record.match_id,
        "recommendation": build_recommendation_response(recommendation_result),
        "recommendation_groups": _build_recommendation_groups_response(
            grouped_results,
            grouped_explanations,
        ),
        "explanation": (
            build_explanation_response(explanation_result)
            if explanation_result is not None
            else None
        ),
        "metadata": {
            "quote_count": len(quote_pool.quote_ingestion_results),
            "quote_pool_ready": True,
            "candidate_vendor_matching_executed": candidate_vendor_record is not None,
            "selected_vendor_names": selected_vendor_names or [],
            "requested_vendor_names": (
                list(candidate_vendor_record.requested_vendor_names)
                if candidate_vendor_record is not None
                else []
            ),
            "candidate_vendor_filter_applied": False,
            "grouped_by_product_group": len(grouped_results) > 1,
            "product_group_counts": recommendation_result.metadata.get(
                "product_group_counts",
                {},
            ),
        },
    }


def get_matches(project_id: str, product_group: str | None = None) -> dict[str, Any]:
    project = _require_project(project_id)
    quote_pool = _require_quote_pool(project_id)
    match = store.get_latest_match(project_id)
    if match is None:
        raise KeyError("match 결과가 없습니다.")
    selected_product_group = canonicalize_product_group(product_group)

    return {
        "project_id": project_id,
        "match_id": match.match_id,
        "project": {
            "project_id": project.project_id,
            "company_name": project.company_name,
            "location": project.location,
            "deadline": project.deadline,
        },
        "requirement": build_project_response(project),
        "quote_pool": {
            "quote_pool_id": quote_pool.quote_pool_id,
            "quote_count": len(quote_pool.quote_ingestion_results),
            "failed_files": quote_pool.failed_files,
        },
        "recommendation": _select_recommendation_response(
            match.recommendation_result,
            selected_product_group,
        ),
        "recommendation_groups": _stored_recommendation_groups_response(
            match.recommendation_result,
            selected_product_group,
        ),
        "explanation": (
            build_explanation_response(match.explanation_result)
            if match.explanation_result is not None
            else None
        ),
    }


def get_explanation(project_id: str, match_id: str, provider_type: str | None = None) -> dict[str, Any]:
    match = _require_match(project_id, match_id)
    if match.explanation_result is None:
        match.explanation_result = _generate_explanation(
            match.recommendation_result,
            provider_type,
        )
        store.update_match_explanation(
            project_id=project_id,
            match_id=match_id,
            explanation_result=match.explanation_result,
        )
    return {
        "project_id": project_id,
        "match_id": match_id,
        **build_explanation_response(match.explanation_result),
    }


def compare_quotes(
    project_id: str,
    payload: CompareRequest,
    product_group: str | None = None,
) -> dict[str, Any]:
    project = _require_project(project_id)
    quote_pool = _require_quote_pool(project_id)
    match = store.get_latest_match(project_id)
    project_install_location = _resolve_project_install_location(project)
    if match and (getattr(match.recommendation_result, "metadata", {}) or {}).get(
        "grouped_by_product_group"
    ):
        return build_grouped_compare_response(
            project_id=project_id,
            quote_results=quote_pool.quote_ingestion_results,
            recommendation_result=match.recommendation_result,
            product_group=product_group,
            quote_ids=payload.quote_ids,
            top_n=payload.top_n,
            project_install_location=project_install_location,
        )
    return build_compare_response(
        project_id=project_id,
        quote_results=quote_pool.quote_ingestion_results,
        recommendation_result=match.recommendation_result if match else None,
        quote_ids=payload.quote_ids,
        top_n=payload.top_n,
        project_install_location=project_install_location,
    )


def _build_recommendation_groups_response(
    grouped_results: dict[str, Any],
    grouped_explanations: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    explanations = grouped_explanations or {}
    groups = []
    for product_group, result in grouped_results.items():
        groups.append(
            {
                "product_group": product_group,
                "quote_count": result.metadata.get(
                    "product_group_quote_count",
                    len(result.all_items),
                ),
                "recommendation": build_recommendation_response(result),
                "explanation": (
                    build_explanation_response(explanations[product_group])
                    if product_group in explanations
                    else None
                ),
            }
        )
    return groups


def _stored_recommendation_groups_response(
    recommendation_result,
    product_group: str | None = None,
) -> list[dict[str, Any]]:
    metadata = getattr(recommendation_result, "metadata", {}) or {}
    stored_results = metadata.get("product_group_results", {}) or {}
    stored_explanations = metadata.get("product_group_explanations", {}) or {}
    groups = []
    for group_name in metadata.get("group_order", list(stored_results.keys())):
        if product_group and canonicalize_product_group(group_name) != product_group:
            continue
        group_result = stored_results.get(group_name)
        if not group_result:
            continue
        recommendation = build_recommendation_response(group_result)
        groups.append(
            {
                "product_group": group_name,
                "quote_count": (
                    group_result.get("metadata", {}) or {}
                ).get(
                    "product_group_quote_count",
                    len(group_result.get("all_items", []) or []),
                ),
                "recommendation": recommendation,
                "explanation": stored_explanations.get(group_name),
            }
        )
    return groups


def _select_recommendation_response(
    recommendation_result,
    product_group: str | None,
) -> dict[str, Any]:
    if not product_group:
        return build_recommendation_response(recommendation_result)
    groups = _stored_recommendation_groups_response(
        recommendation_result,
        product_group,
    )
    if groups:
        return groups[0]["recommendation"]
    return build_recommendation_response(recommendation_result)


def _resolve_project_install_location(project) -> str | None:
    requirement_result = getattr(project, "requirement_result", None)
    requirement = getattr(requirement_result, "requirement", None)
    return _normalize_project_location(
        getattr(requirement, "region", None)
    ) or _normalize_project_location(getattr(project, "location", None))


def _normalize_project_location(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in {"", "미입력", "없음", "null", "undefined", "none"}:
        return None
    return text


def run_candidate_vendors(
    project_id: str,
    payload: CandidateVendorsRequest | None = None,
) -> dict[str, Any]:
    project = _require_project(project_id)
    if payload is not None and not isinstance(payload, CandidateVendorsRequest):
        raise TypeError(
            "run_candidate_vendors expected CandidateVendorsRequest or None, "
            f"got {type(payload).__name__}"
        )
    payload = payload or CandidateVendorsRequest()
    top_n = payload.top_n or 10
    similarity_threshold = payload.similarity_threshold
    requirement_result = _resolve_candidate_requirement_result(project, payload)
    if not getattr(requirement_result, "embedding_vector", None):
        raise ValueError("requirement embedding_vector is required for candidate-vendors.")

    pipeline = create_partner_matching_pipeline()
    result = pipeline.run(
        requirement_result,
        top_n=top_n,
        similarity_threshold=similarity_threshold,
    )
    result.metadata["lazy_hydration_used"] = bool(
        (getattr(requirement_result, "metadata", {}) or {}).get("lazy_hydration_used")
    )
    record = store.save_candidate_vendors(
        project_id=project_id,
        requirement_result=requirement_result,
        candidate_vendor_result=result,
        top_n=top_n,
        similarity_threshold=similarity_threshold,
        requested_vendor_names=payload.requested_vendor_names,
    )
    return build_candidate_vendors_response(project_id, record)


def get_candidate_vendors(project_id: str) -> dict[str, Any]:
    _require_project(project_id)
    record = store.get_candidate_vendors(project_id)
    if record is None:
        return build_candidate_vendors_not_found_response(project_id)
    return build_candidate_vendors_response(project_id, record)


def _resolve_candidate_requirement_result(project, payload: CandidateVendorsRequest):
    if _has_candidate_requirement_override(payload):
        payload_dict = {
            "company_name": payload.customer_name or project.company_name,
            "location": payload.region or project.location,
            "deadline": payload.install_schedule_text or project.deadline,
            "request_text": payload.request_text or _build_candidate_requirement_text(project, payload),
            "products": payload.products or [],
        }
        requirement_info = build_requirement_info_from_project_payload_dict(
            payload_dict,
            request_id=project.request_id,
        )
        requirement_info.metadata["candidate_override"] = True
        requirement_info.metadata["save_as_project_requirement"] = False
        pipeline = create_requirement_ingestion_pipeline()
        return pipeline.process_requirement_info(
            requirement_info,
            request_id=project.request_id,
        )

    if not getattr(project, "requirement_result", None):
        return hydrate_project_requirement_result_if_missing(project)
    return project.requirement_result


def hydrate_project_requirement_result_if_missing(project):
    if getattr(project, "requirement_result", None) is not None:
        return project.requirement_result

    payload_dict = {
        "company_name": project.company_name,
        "location": project.location,
        "deadline": project.deadline,
        "request_text": project.request_text or project.original_request_text or "",
    }
    requirement_info = build_requirement_info_from_project_payload_dict(
        payload_dict,
        request_id=project.request_id,
    )
    requirement_info.metadata["lazy_hydration_used"] = True
    requirement_info.metadata["lazy_hydration_reason"] = (
        "requirement_result missing for persisted project"
    )
    pipeline = create_requirement_ingestion_pipeline()
    requirement_result = pipeline.process_requirement_info(
        requirement_info,
        request_id=project.request_id,
    )
    requirement_result.metadata["lazy_hydration_used"] = True
    requirement_result.metadata["lazy_hydration_reason"] = (
        "requirement_result missing for persisted project"
    )
    store.update_project_requirement_result(
        project_id=project.project_id,
        requirement_result=requirement_result,
    )
    return requirement_result


def _has_candidate_requirement_override(payload: CandidateVendorsRequest) -> bool:
    return any(
        [
            bool((payload.request_text or "").strip()),
            bool((payload.customer_name or "").strip()),
            bool((payload.region or "").strip()),
            bool((payload.install_schedule_text or "").strip()),
            bool(payload.products),
        ]
    )


def _build_candidate_requirement_text(project, payload: CandidateVendorsRequest) -> str:
    if payload.request_text and payload.request_text.strip():
        return payload.request_text

    lines = []
    customer_name = payload.customer_name or project.company_name
    region = payload.region or project.location
    install_schedule = payload.install_schedule_text or project.deadline
    if customer_name:
        lines.append(f"customer_name: {customer_name}")
    if region:
        lines.append(f"region: {region}")
    if install_schedule:
        lines.append(f"install_schedule: {install_schedule}")
    for index, product in enumerate(payload.products or [], start=1):
        fields = [
            f"{key}: {value}"
            for key, value in product.items()
            if value is not None and value != ""
        ]
        if fields:
            lines.append(f"product_{index}: " + ", ".join(fields))
    if not lines:
        return project.request_text or ""
    return "\n".join(lines)


def _attach_candidate_vendor_links(project_id: str, quote_results: list[Any]) -> None:
    candidate_record = store.get_candidate_vendors(project_id)
    if candidate_record is None:
        return

    selected_vendor_names = list(candidate_record.selected_vendor_names)
    for result in quote_results:
        quote = getattr(result, "quote", None)
        vendor_name = getattr(quote, "vendor_name", None)
        matched_vendor_name = _match_selected_vendor_name(vendor_name, selected_vendor_names)
        metadata = getattr(result, "metadata", None)
        if metadata is None:
            metadata = {}
            result.metadata = metadata
        metadata["candidate_vendor_link"] = {
            "candidate_vendor_matching_executed": True,
            "is_selected_vendor": matched_vendor_name is not None,
            "matched_vendor_name": matched_vendor_name,
        }


def _match_selected_vendor_name(
    vendor_name: str | None,
    selected_vendor_names: list[str],
) -> str | None:
    normalized_vendor = _normalize_vendor_name(vendor_name)
    if not normalized_vendor:
        return None
    for selected_name in selected_vendor_names:
        normalized_selected = _normalize_vendor_name(selected_name)
        if (
            normalized_selected
            and (
                normalized_vendor == normalized_selected
                or normalized_vendor in normalized_selected
                or normalized_selected in normalized_vendor
            )
        ):
            return selected_name
    return None


def _normalize_vendor_name(value: str | None) -> str:
    text = value or ""
    text = text.replace("(주)", "")
    text = text.replace("주식회사", "")
    return "".join(ch.lower() for ch in text if ch.isalnum())


def _generate_explanation(recommendation_result, provider_type: str | None = None):
    selected = provider_type or os.getenv("EXPLANATION_PROVIDER") or (
        "azure_openai" if os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT") else "template"
    )
    try:
        return create_explanation_provider(selected).generate(recommendation_result)
    except Exception:
        fallback = create_explanation_provider("template").generate(recommendation_result)
        fallback.provider = "template_fallback"
        fallback.warnings.append(f"{selected} provider 실패로 template fallback 사용")
        return fallback


def _require_project(project_id: str):
    project = store.get_project(project_id)
    if project is None:
        raise KeyError(f"project_id를 찾을 수 없습니다: {project_id}")
    return project


def _require_quote_pool(project_id: str):
    quote_pool = store.get_quote_pool(project_id)
    if quote_pool is None:
        raise KeyError("quote pool이 없습니다. 먼저 견적서를 업로드하세요.")
    return quote_pool


def _require_match(project_id: str, match_id: str):
    match = store.get_match(project_id, match_id)
    if match is None:
        raise KeyError(f"match_id를 찾을 수 없습니다: {match_id}")
    return match
