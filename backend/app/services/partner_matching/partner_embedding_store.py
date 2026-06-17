import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
import logging

from config.paths import PARTNER_EMBEDDINGS_PATH
from services.partner_matching.partner_embedding_text_builder import (
    build_partner_embedding_text,
)
from services.partner_matching.schemas import PartnerEmbeddingRecord
from services.ranking.schemas import PartnerProfile


DEFAULT_PARTNER_EMBEDDING_PATH = PARTNER_EMBEDDINGS_PATH
PARTNER_EMBEDDING_CACHE_SCHEMA_VERSION = 2
logger = logging.getLogger(__name__)


def load_partner_embeddings(
    path: Path = DEFAULT_PARTNER_EMBEDDING_PATH,
    *,
    expected_dimension: int | None = None,
) -> dict[str, PartnerEmbeddingRecord]:
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
    raw_records = data.get("records", data) if isinstance(data, dict) else {}
    cached_dimension = metadata.get("embedding_dimension")
    if expected_dimension is not None and cached_dimension is not None:
        try:
            cached_dimension_value = int(cached_dimension)
        except (TypeError, ValueError):
            cached_dimension_value = None
        if cached_dimension_value != expected_dimension:
            logger.warning(
                "Partner embedding cache dimension mismatch detected. "
                "Rebuilding cache. expected_dim=%s cached_dim=%s",
                expected_dimension,
                cached_dimension,
            )
            return {}

    records = {}
    for partner_name, raw_record in (raw_records or {}).items():
        try:
            records[partner_name] = PartnerEmbeddingRecord(**raw_record)
        except TypeError:
            continue
    if expected_dimension is not None and not _is_cache_dimension_valid(
        records,
        expected_dimension=expected_dimension,
    ):
        cached_dim = _first_record_dimension(records)
        logger.warning(
            "Partner embedding record dimension mismatch detected. "
            "Rebuilding cache. expected_dim=%s cached_dim=%s",
            expected_dimension,
            cached_dim,
        )
        return {}
    return records


def save_partner_embeddings(
    records: dict[str, PartnerEmbeddingRecord],
    path: Path = DEFAULT_PARTNER_EMBEDDING_PATH,
    *,
    embedding_provider: Any | None = None,
    embedding_dimension: int | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if embedding_dimension is None:
        embedding_dimension = _first_record_dimension(records)
    payload = {
        "metadata": {
            "schema_version": PARTNER_EMBEDDING_CACHE_SCHEMA_VERSION,
            "embedding_provider": (
                embedding_provider.__class__.__name__
                if embedding_provider is not None
                else None
            ),
            "embedding_dimension": embedding_dimension,
        },
        "records": {
            partner_name: asdict(record)
            for partner_name, record in records.items()
        },
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_source_hash(partner: PartnerProfile) -> str:
    payload: dict[str, Any] = {
        "name": partner.name,
        "specialty_tags": partner.specialty_tags,
        "is_premium": partner.is_premium,
        "success_rate": partner.success_rate,
        "response_speed": partner.response_speed,
        "financial_status": partner.financial_status,
        "is_excluded": partner.is_excluded,
        "solution_breakdown": partner.solution_breakdown,
        "industry_breakdown": partner.industry_breakdown,
        "scale_breakdown": partner.scale_breakdown,
        "installation_count": partner.installation_count,
        "company_location": partner.company_location,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_or_create_partner_embeddings(
    partners: list[PartnerProfile],
    embedding_provider,
    path: Path = DEFAULT_PARTNER_EMBEDDING_PATH,
    *,
    expected_dimension: int | None = None,
) -> dict[str, PartnerEmbeddingRecord]:
    records = load_partner_embeddings(path, expected_dimension=expected_dimension)
    updated = _cache_metadata_needs_refresh(
        path,
        expected_dimension=expected_dimension,
    )

    for partner in partners:
        source_hash = build_source_hash(partner)
        existing = records.get(partner.name)
        if (
            existing
            and existing.source_hash == source_hash
            and existing.embedding_vector
            and (
                expected_dimension is None
                or len(existing.embedding_vector) == expected_dimension
            )
        ):
            continue

        embedding_text = build_partner_embedding_text(partner)
        embedding_vector = embedding_provider.embed_text(embedding_text)
        if expected_dimension is not None and len(embedding_vector) != expected_dimension:
            raise RuntimeError(
                "Partner embedding provider returned unexpected dimension: "
                f"expected={expected_dimension}, actual={len(embedding_vector)}"
            )
        records[partner.name] = PartnerEmbeddingRecord(
            partner_name=partner.name,
            embedding_text=embedding_text,
            embedding_vector=list(embedding_vector),
            embedding_dim=len(embedding_vector),
            source_hash=source_hash,
            metadata={
                "specialty_tags": partner.specialty_tags,
                "is_premium": partner.is_premium,
                "solution_breakdown": partner.solution_breakdown,
                "industry_breakdown": partner.industry_breakdown,
                "scale_breakdown": partner.scale_breakdown,
                "installation_count": partner.installation_count,
                "company_location": partner.company_location,
            },
        )
        updated = True

    if updated:
        save_partner_embeddings(
            records,
            path,
            embedding_provider=embedding_provider,
            embedding_dimension=expected_dimension,
        )

    if expected_dimension is not None and not _is_cache_dimension_valid(
        records,
        expected_dimension=expected_dimension,
    ):
        invalid_dim = _first_record_dimension(records)
        raise RuntimeError(
            "Partner embedding dimension mismatch after rebuild: "
            f"expected={expected_dimension}, actual={invalid_dim}"
        )
    return records


def _embedding_dim(vector: list[float] | None) -> int | None:
    return len(vector) if isinstance(vector, list) else None


def _is_cache_dimension_valid(
    records: dict[str, PartnerEmbeddingRecord],
    *,
    expected_dimension: int,
) -> bool:
    return all(
        _embedding_dim(record.embedding_vector) == expected_dimension
        for record in records.values()
    )


def _first_record_dimension(
    records: dict[str, PartnerEmbeddingRecord],
) -> int | None:
    for record in records.values():
        return _embedding_dim(record.embedding_vector)
    return None


def _cache_metadata_needs_refresh(
    path: Path,
    *,
    expected_dimension: int | None,
) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(data, dict):
        return False
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return True
    if metadata.get("schema_version") != PARTNER_EMBEDDING_CACHE_SCHEMA_VERSION:
        return True
    if expected_dimension is None:
        return False
    try:
        cached_dimension = int(metadata.get("embedding_dimension"))
    except (TypeError, ValueError):
        return True
    return cached_dimension != expected_dimension
