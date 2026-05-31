import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from services.partner_matching.partner_embedding_text_builder import (
    build_partner_embedding_text,
)
from services.partner_matching.schemas import PartnerEmbeddingRecord
from services.ranking.schemas import PartnerProfile


DEFAULT_PARTNER_EMBEDDING_PATH = Path("data/partner_embeddings.json")


def load_partner_embeddings(
    path: Path = DEFAULT_PARTNER_EMBEDDING_PATH,
) -> dict[str, PartnerEmbeddingRecord]:
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    records = {}
    for partner_name, raw_record in data.items():
        try:
            records[partner_name] = PartnerEmbeddingRecord(**raw_record)
        except TypeError:
            continue
    return records


def save_partner_embeddings(
    records: dict[str, PartnerEmbeddingRecord],
    path: Path = DEFAULT_PARTNER_EMBEDDING_PATH,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        partner_name: asdict(record)
        for partner_name, record in records.items()
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
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_or_create_partner_embeddings(
    partners: list[PartnerProfile],
    embedding_provider,
    path: Path = DEFAULT_PARTNER_EMBEDDING_PATH,
) -> dict[str, PartnerEmbeddingRecord]:
    records = load_partner_embeddings(path)
    updated = False

    for partner in partners:
        source_hash = build_source_hash(partner)
        existing = records.get(partner.name)
        if existing and existing.source_hash == source_hash and existing.embedding_vector:
            continue

        embedding_text = build_partner_embedding_text(partner)
        embedding_vector = embedding_provider.embed_text(embedding_text)
        records[partner.name] = PartnerEmbeddingRecord(
            partner_name=partner.name,
            embedding_text=embedding_text,
            embedding_vector=list(embedding_vector),
            embedding_dim=len(embedding_vector),
            source_hash=source_hash,
            metadata={
                "specialty_tags": partner.specialty_tags,
                "is_premium": partner.is_premium,
            },
        )
        updated = True

    if updated:
        save_partner_embeddings(records, path)

    return records
