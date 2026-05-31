import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from services.api_demo.response_builders import (
    build_compare_response,
    build_explanation_response,
    build_project_response,
    build_quote_upload_response,
    build_recommendation_response,
)
from services.api_demo.schemas import (
    CompareRequest,
    MatchRunRequest,
    ProjectCreateRequest,
)
from services.api_demo.store import store
from services.explanation.factory import create_explanation_provider
from services.partner_matching.factory import create_partner_matching_pipeline
from services.quote_ingestion.factory import create_quote_ingestion_pipeline
from services.recommendation.factory import create_recommendation_pipeline
from services.requirement_ingestion.factory import create_requirement_ingestion_pipeline


SUPPORTED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls"}


def create_project(payload: ProjectCreateRequest) -> dict[str, Any]:
    request_id = f"request_{uuid4().hex[:8]}"
    pipeline = create_requirement_ingestion_pipeline()
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
    )
    return build_project_response(record)


def upload_quote_paths(project_id: str, file_paths: list[Path]) -> dict[str, Any]:
    project = _require_project(project_id)
    upload_dir = Path("data/api_demo_uploads") / project_id
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

    pipeline = create_recommendation_pipeline("rule")
    recommendation_result = pipeline.recommend(
        project.requirement_result,
        quote_pool.quote_ingestion_results,
        top_n=payload.quote_top_n,
    )
    explanation_result = None
    if payload.run_explanation:
        explanation_result = _generate_explanation(
            recommendation_result,
            payload.explanation_provider,
        )

    match_record = store.save_match(
        project_id=project_id,
        recommendation_result=recommendation_result,
        explanation_result=explanation_result,
    )
    return {
        "project_id": project_id,
        "match_id": match_record.match_id,
        "recommendation": build_recommendation_response(recommendation_result),
        "explanation": (
            build_explanation_response(explanation_result)
            if explanation_result is not None
            else None
        ),
        "metadata": {
            "quote_count": len(quote_pool.quote_ingestion_results),
            "quote_pool_ready": True,
        },
    }


def get_matches(project_id: str) -> dict[str, Any]:
    project = _require_project(project_id)
    quote_pool = _require_quote_pool(project_id)
    match = store.get_latest_match(project_id)
    if match is None:
        raise KeyError("match 결과가 없습니다.")

    return {
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
        "recommendation": build_recommendation_response(match.recommendation_result),
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
    return {
        "project_id": project_id,
        "match_id": match_id,
        **build_explanation_response(match.explanation_result),
    }


def compare_quotes(project_id: str, payload: CompareRequest) -> dict[str, Any]:
    quote_pool = _require_quote_pool(project_id)
    match = store.get_latest_match(project_id)
    return build_compare_response(
        project_id=project_id,
        quote_results=quote_pool.quote_ingestion_results,
        recommendation_result=match.recommendation_result if match else None,
        quote_ids=payload.quote_ids,
        top_n=payload.top_n,
    )


def run_candidate_vendors(project_id: str, top_n: int = 10) -> dict[str, Any]:
    project = _require_project(project_id)
    pipeline = create_partner_matching_pipeline()
    result = pipeline.run(project.requirement_result, top_n=top_n)
    return {
        "project_id": project_id,
        "top_n": top_n,
        "candidates": [
            {
                "partner_name": candidate.partner_name,
                "semantic_similarity_score": candidate.semantic_similarity_score,
                "specialty_tags": candidate.specialty_tags,
                "is_premium": candidate.is_premium,
                "success_rate": candidate.success_rate,
                "response_speed": candidate.response_speed,
                "financial_status": candidate.financial_status,
                "filter_reasons": candidate.filter_reasons,
            }
            for candidate in result.candidates
        ],
        "filtered_count": len(result.filtered_candidates),
    }


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
