import json
from pathlib import Path
from tempfile import TemporaryDirectory

from services.partner_matching.partner_embedding_store import (
    build_source_hash,
    get_or_create_partner_embeddings,
    save_partner_embeddings,
)
from services.partner_matching.partner_matching_pipeline import PartnerMatchingPipeline
from services.partner_matching.schemas import PartnerEmbeddingRecord
from services.ranking.schemas import PartnerProfile
from services.requirement.schemas import RequirementInfo
from services.requirement_ingestion.schemas import RequirementIngestionResult
from services.similarity.cosine_similarity_provider import CosineSimilarityProvider


class FakeEmbeddingProvider:
    def __init__(self, dimension: int) -> None:
        self.dimension = dimension
        self.calls = 0

    def embed_text(self, text: str) -> list[float]:
        self.calls += 1
        base = (sum(ord(ch) for ch in text) % 17) / 100.0
        return [base + ((index + 1) / self.dimension) for index in range(self.dimension)]


def _partner(name: str = "테스트공급사") -> PartnerProfile:
    return PartnerProfile(
        name=name,
        specialty_tags=["LED전광판"],
        is_premium=False,
        success_rate=0.9,
        response_speed="fast",
        financial_status="good",
        is_excluded=False,
        installation_count=12,
        solution_breakdown={"LED전광판": 12},
    )


def _write_stale_cache(path: Path, partner: PartnerProfile, dimension: int) -> None:
    stale_record = PartnerEmbeddingRecord(
        partner_name=partner.name,
        embedding_text="stale text",
        embedding_vector=[0.01] * dimension,
        embedding_dim=dimension,
        source_hash=build_source_hash(partner),
        metadata={},
    )
    save_partner_embeddings(
        {partner.name: stale_record},
        path,
        embedding_provider=FakeEmbeddingProvider(dimension),
        embedding_dimension=dimension,
    )


def test_mismatched_partner_cache_is_rebuilt() -> None:
    partner = _partner()
    with TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "partner_embeddings.json"
        _write_stale_cache(cache_path, partner, dimension=1536)

        provider = FakeEmbeddingProvider(dimension=3072)
        records = get_or_create_partner_embeddings(
            [partner],
            provider,
            path=cache_path,
            expected_dimension=3072,
        )

        assert provider.calls == 1
        assert len(records[partner.name].embedding_vector) == 3072
        saved = json.loads(cache_path.read_text(encoding="utf-8"))
        assert saved["metadata"]["embedding_dimension"] == 3072
        assert saved["metadata"]["schema_version"] == 2


def test_matching_dimension_cache_is_reused() -> None:
    partner = _partner()
    with TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "partner_embeddings.json"
        valid_record = PartnerEmbeddingRecord(
            partner_name=partner.name,
            embedding_text="valid text",
            embedding_vector=[0.02] * 3072,
            embedding_dim=3072,
            source_hash=build_source_hash(partner),
            metadata={},
        )
        save_partner_embeddings(
            {partner.name: valid_record},
            cache_path,
            embedding_provider=FakeEmbeddingProvider(3072),
            embedding_dimension=3072,
        )

        provider = FakeEmbeddingProvider(dimension=3072)
        records = get_or_create_partner_embeddings(
            [partner],
            provider,
            path=cache_path,
            expected_dimension=3072,
        )

        assert provider.calls == 0
        assert len(records[partner.name].embedding_vector) == 3072


def test_legacy_matching_dimension_cache_gets_metadata_without_reembedding() -> None:
    partner = _partner()
    with TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "partner_embeddings.json"
        legacy_record = PartnerEmbeddingRecord(
            partner_name=partner.name,
            embedding_text="legacy valid text",
            embedding_vector=[0.03] * 3072,
            embedding_dim=3072,
            source_hash=build_source_hash(partner),
            metadata={},
        )
        cache_path.write_text(
            json.dumps({partner.name: legacy_record.__dict__}, ensure_ascii=False),
            encoding="utf-8",
        )

        provider = FakeEmbeddingProvider(dimension=3072)
        records = get_or_create_partner_embeddings(
            [partner],
            provider,
            path=cache_path,
            expected_dimension=3072,
        )

        assert provider.calls == 0
        assert len(records[partner.name].embedding_vector) == 3072
        saved = json.loads(cache_path.read_text(encoding="utf-8"))
        assert saved["metadata"]["embedding_dimension"] == 3072
        assert saved["metadata"]["schema_version"] == 2


def test_partner_matching_pipeline_rebuilds_stale_cache_before_similarity() -> None:
    partner = _partner()
    with TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "partner_embeddings.json"
        _write_stale_cache(cache_path, partner, dimension=2)

        requirement = RequirementInfo(
            raw_text="LED전광판 설치",
            customer_name="테스트고객",
            category="LED전광판",
            request_summary="LED전광판 설치",
            required_keywords=["LED전광판"],
        )
        requirement_result = RequirementIngestionResult(
            request_id="request_dimension_guard",
            source_type="test",
            source_path=None,
            requirement=requirement,
            embedding_text="LED전광판 설치",
            embedding_vector=[0.2, 0.3, 0.4],
            embedding_dim=3,
            raw_text_preview="LED전광판 설치",
        )
        provider = FakeEmbeddingProvider(dimension=3)
        pipeline = PartnerMatchingPipeline(
            embedding_provider=provider,
            similarity_provider=CosineSimilarityProvider(),
            partner_profiles=[partner],
            partner_embedding_path=cache_path,
        )

        result = pipeline.run(requirement_result, top_n=1)

        assert provider.calls == 1
        assert result.all_candidates
        assert result.metadata["expected_embedding_dimension"] == 3
        saved = json.loads(cache_path.read_text(encoding="utf-8"))
        saved_records = saved["records"]
        assert len(saved_records[partner.name]["embedding_vector"]) == 3


def test_partner_embedding_provider_dimension_mismatch_fails_fast() -> None:
    partner = _partner()
    with TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "partner_embeddings.json"
        provider = FakeEmbeddingProvider(dimension=2)
        try:
            get_or_create_partner_embeddings(
                [partner],
                provider,
                path=cache_path,
                expected_dimension=3,
            )
        except RuntimeError as exc:
            assert "unexpected dimension" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError for provider dimension mismatch")


if __name__ == "__main__":
    test_mismatched_partner_cache_is_rebuilt()
    test_matching_dimension_cache_is_reused()
    test_legacy_matching_dimension_cache_gets_metadata_without_reembedding()
    test_partner_matching_pipeline_rebuilds_stale_cache_before_similarity()
    test_partner_embedding_provider_dimension_mismatch_fails_fast()
    print("test_partner_embedding_dimension_guard passed")
