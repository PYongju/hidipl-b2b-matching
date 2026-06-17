from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any

from config.paths import PARTNER_EMBEDDINGS_PATH
from services.partner_matching.partner_embedding_store import (
    get_or_create_partner_embeddings,
)
from services.partner_matching.partner_matching_provider import PartnerMatchingProvider
from services.partner_matching.schemas import PartnerMatchingResult
from services.ranking.schemas import PartnerProfile
from services.requirement_ingestion.schemas import RequirementIngestionResult


class PartnerMatchingPipeline:
    def __init__(
        self,
        embedding_provider,
        similarity_provider,
        partner_profiles: list[PartnerProfile],
        partner_embedding_path=PARTNER_EMBEDDINGS_PATH,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.similarity_provider = similarity_provider
        self.partner_profiles = partner_profiles
        self.partner_embedding_path = partner_embedding_path

    def run(
        self,
        requirement_result: RequirementIngestionResult,
        *,
        top_n: int = 10,
        similarity_threshold: float = 60.0,
    ) -> PartnerMatchingResult:
        if not requirement_result.embedding_vector:
            raise ValueError("요구사항 임베딩이 없어 PartnerMatching을 실행할 수 없습니다.")

        expected_dimension = len(requirement_result.embedding_vector)
        cache_existed_before = self.partner_embedding_path.exists()
        partner_embeddings = get_or_create_partner_embeddings(
            self.partner_profiles,
            self.embedding_provider,
            path=self.partner_embedding_path,
            expected_dimension=expected_dimension,
        )
        invalid_dimensions = {
            partner_name: len(record.embedding_vector or [])
            for partner_name, record in partner_embeddings.items()
            if len(record.embedding_vector or []) != expected_dimension
        }
        if invalid_dimensions:
            sample_dimension = next(iter(invalid_dimensions.values()))
            raise RuntimeError(
                "Partner embedding dimension mismatch after rebuild: "
                f"expected={expected_dimension}, actual={sample_dimension}"
            )
        provider = PartnerMatchingProvider(
            partners=self.partner_profiles,
            partner_embeddings=partner_embeddings,
            similarity_provider=self.similarity_provider,
            similarity_threshold=similarity_threshold,
        )
        result = provider.match(
            requirement_result.requirement,
            requirement_result.embedding_vector,
            top_n=top_n,
        )
        result.request_id = requirement_result.request_id
        result.metadata.update(
            {
                "provider": provider.__class__.__name__,
                "embedding_provider": self.embedding_provider.__class__.__name__,
                "similarity_provider": self.similarity_provider.__class__.__name__,
                "embedding_cache_used": cache_existed_before,
                "expected_embedding_dimension": expected_dimension,
                "partner_vector_count": len(partner_embeddings),
            }
        )
        return result

    def to_storage_dict(self, result: PartnerMatchingResult) -> dict[str, Any]:
        data = asdict(result)
        return self._to_jsonable(data)

    def _to_jsonable(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                key: self._to_jsonable(item)
                for key, item in value.items()
                if key != "embedding_vector"
            }
        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value]
        return value
