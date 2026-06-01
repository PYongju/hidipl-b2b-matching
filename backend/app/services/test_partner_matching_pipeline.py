from pathlib import Path
from pprint import pprint

from config.paths import PARTNER_EMBEDDINGS_PATH
from services.config import get_settings
from services.partner_matching.factory import create_partner_matching_pipeline
from services.partner_matching.partner_matching_provider import PartnerMatchingProvider
from services.partner_matching.schemas import PartnerEmbeddingRecord
from services.ranking.schemas import PartnerProfile
from services.requirement.schemas import RequirementInfo
from services.requirement_ingestion.factory import create_requirement_ingestion_pipeline
from services.similarity.factory import create_similarity_provider


class FakeEmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        normalized = text.replace(" ", "").lower()
        if "가구" in normalized or "인테리어" in normalized:
            return [0.0, 1.0, 0.0]
        if "제외" in normalized:
            return [0.8, 0.2, 0.0]
        return [1.0, 0.0, 0.0]


def run_offline_unit_test() -> None:
    print("\n========== Partner Matching Offline Unit Test ==========")
    partners = [
        PartnerProfile("파트너A", ["LED 전광판", "설치"], True, 0.10, "fast", "normal", False),
        PartnerProfile("파트너B", ["비디오월", "디지털 사이니지"], False, 0.08, "normal", "good", False),
        PartnerProfile("파트너C", ["인테리어", "가구"], False, 0.03, "normal", "normal", False),
        PartnerProfile("파트너D", ["LED 전광판"], False, 0.0, "slow", "caution", True),
    ]
    embedding_provider = FakeEmbeddingProvider()
    records = {
        partner.name: PartnerEmbeddingRecord(
            partner_name=partner.name,
            embedding_text=", ".join(partner.specialty_tags),
            embedding_vector=embedding_provider.embed_text(", ".join(partner.specialty_tags)),
            embedding_dim=3,
            source_hash="offline",
        )
        for partner in partners
    }
    requirement = RequirementInfo(
        raw_text="회의실 디지털 사이니지 또는 LED 전광판 설치",
        customer_name="테스트고객",
        request_summary="회의실 디지털 사이니지 또는 LED 전광판 설치",
        required_keywords=["디지털 사이니지", "LED 전광판", "설치"],
    )
    provider = PartnerMatchingProvider(
        partners=partners,
        partner_embeddings=records,
        similarity_provider=create_similarity_provider("cosine"),
        similarity_threshold=80.0,
    )
    result = provider.match(requirement, [1.0, 0.0, 0.0], top_n=10)

    print_partner_matching_result(result)


def run_azure_integration_test() -> None:
    print("\n========== Partner Matching Azure Integration Test ==========")
    requirement_text = """신규 프로젝트 연결드립니다.

1. 고객사: 스노우스페이스
2. 견적 요청 내용: 커브드 LED전광판 + 평면 LED전광판
(1) 커브드 LED 전광판
- 사이즈 : 12,000 × 3,000
- Pitch : 2.5 이하
(2) 플랫 LED전광판
- 사이즈 : 7,150 × 2,700
- Pitch : 2.5 이하
3. 설치 일정: 2월말~3월초
4. 지역: 서울 홍대(동교동)
"""
    try:
        settings = get_settings()
        requirement_pipeline = create_requirement_ingestion_pipeline(settings)
        requirement_result = requirement_pipeline.process_text(
            requirement_text,
            request_id="partner_matching_integration_test",
        )
        pipeline = create_partner_matching_pipeline(settings)
        result = pipeline.run(requirement_result, top_n=10, similarity_threshold=60.0)
    except Exception as e:
        print(f"Azure integration test를 실행하지 못했습니다: {e}")
        return

    print_partner_matching_result(result)
    print("partner embedding cache exists:", PARTNER_EMBEDDINGS_PATH.exists())


def print_partner_matching_result(result) -> None:
    print("request_id:", result.request_id)
    print("customer_name:", result.customer_name)
    print("top_n:", result.top_n)
    print("filtered count:", len(result.filtered_candidates))
    print("candidates:")
    for candidate in result.candidates:
        print()
        print("partner_name:", candidate.partner_name)
        print("semantic_similarity_score:", candidate.semantic_similarity_score)
        print("cosine_similarity:", candidate.cosine_similarity)
        print("specialty_tags:")
        pprint(candidate.specialty_tags)
        print("is_premium:", candidate.is_premium)
        print("success_rate:", candidate.success_rate)
        print("response_speed:", candidate.response_speed)
        print("financial_status:", candidate.financial_status)
        print("business_rule_passed:", candidate.business_rule_passed)
        print("filter_reasons:")
        pprint(candidate.filter_reasons)


def main() -> None:
    run_offline_unit_test()
    run_azure_integration_test()


if __name__ == "__main__":
    main()
