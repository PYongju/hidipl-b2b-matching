from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints


SENSITIVE_KEYS_ALWAYS_REMOVE = {
    "api_key",
    "endpoint",
    "ocr_text",
    "ocr_full_text",
}

API_OUTPUT_REMOVE_KEYS = {
    "embedding_vector",
    "requirement_embedding",
    "partner_embedding",
}


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    return value


def sanitize_for_db_storage(value: Any) -> Any:
    return _remove_keys(to_jsonable(value), SENSITIVE_KEYS_ALWAYS_REMOVE)


def sanitize_for_api_output(value: Any) -> Any:
    return _remove_keys(
        to_jsonable(value),
        SENSITIVE_KEYS_ALWAYS_REMOVE | API_OUTPUT_REMOVE_KEYS,
    )


def serialize_project_record(record: Any) -> dict[str, Any]:
    return sanitize_for_db_storage(record)


def serialize_quote_pool_record(record: Any) -> dict[str, Any]:
    data = sanitize_for_db_storage(record)
    data["uploaded_files"] = [_safe_path_string(path) for path in data.get("uploaded_files") or []]
    return data


def serialize_match_record(record: Any) -> dict[str, Any]:
    return sanitize_for_db_storage(record)


def serialize_candidate_vendor_record(record: Any) -> dict[str, Any]:
    return sanitize_for_db_storage(record)


def deserialize_project_record(data: dict[str, Any]):
    from services.api_demo.store import ProjectRecord
    from services.requirement_ingestion.schemas import RequirementIngestionResult

    payload = dict(data)
    payload["requirement_result"] = _dataclass_from_dict(
        RequirementIngestionResult,
        payload.get("requirement_result"),
    )
    return ProjectRecord(**payload)


def deserialize_quote_pool_record(data: dict[str, Any]):
    from services.api_demo.store import QuotePoolRecord
    from services.quote_ingestion.schemas import QuoteIngestionResult

    payload = dict(data)
    payload["quote_ingestion_results"] = [
        _dataclass_from_dict(QuoteIngestionResult, item)
        for item in payload.get("quote_ingestion_results") or []
    ]
    return QuotePoolRecord(**payload)


def deserialize_match_record(data: dict[str, Any]):
    from services.api_demo.store import MatchRecord
    from services.explanation.schemas import RecommendationExplanationResult
    from services.recommendation.schemas import RecommendationPipelineResult

    payload = dict(data)
    payload["recommendation_result"] = _dataclass_from_dict(
        RecommendationPipelineResult,
        payload.get("recommendation_result"),
    )
    explanation = payload.get("explanation_result")
    payload["explanation_result"] = (
        _dataclass_from_dict(RecommendationExplanationResult, explanation)
        if explanation is not None
        else None
    )
    return MatchRecord(**payload)


def deserialize_candidate_vendor_record(data: dict[str, Any]):
    from services.api_demo.store import CandidateVendorRecord
    from services.partner_matching.schemas import PartnerMatchingResult
    from services.requirement_ingestion.schemas import RequirementIngestionResult

    payload = dict(data)
    payload["requirement_result"] = _dataclass_from_dict(
        RequirementIngestionResult,
        payload.get("requirement_result"),
    )
    payload["candidate_vendor_result"] = _dataclass_from_dict(
        PartnerMatchingResult,
        payload.get("candidate_vendor_result"),
    )
    return CandidateVendorRecord(**payload)


def _remove_keys(value: Any, keys_to_remove: set[str]) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in keys_to_remove:
                continue
            cleaned[key] = _remove_keys(item, keys_to_remove)
        return cleaned
    if isinstance(value, list):
        return [_remove_keys(item, keys_to_remove) for item in value]
    return value


def _safe_path_string(value: Any) -> str:
    text = str(value)
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.relative_to(Path.cwd()))
        except ValueError:
            return path.name
    return text


def _dataclass_from_dict(cls: type, value: Any) -> Any:
    if value is None or not is_dataclass(cls) or not isinstance(value, dict):
        return value

    kwargs = {}
    field_map = {item.name: item for item in fields(cls)}
    type_hints = get_type_hints(cls)
    for key, item in value.items():
        field_info = field_map.get(key)
        if field_info is None:
            continue
        kwargs[key] = _coerce_value(type_hints.get(key, field_info.type), item)
    return cls(**kwargs)


def _coerce_value(annotation: Any, value: Any) -> Any:
    if value is None:
        return None

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in {UnionType, Union}:
        non_none = [arg for arg in args if arg is not type(None)]
        for candidate in non_none:
            try:
                return _coerce_value(candidate, value)
            except Exception:
                continue
        return value

    if origin in {list, tuple}:
        item_type = args[0] if args else Any
        return [_coerce_value(item_type, item) for item in (value or [])]

    if origin is dict:
        return dict(value or {})

    if annotation is datetime and isinstance(value, str):
        return datetime.fromisoformat(value)

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation(value)

    if isinstance(annotation, type) and is_dataclass(annotation):
        return _dataclass_from_dict(annotation, value)

    return value
