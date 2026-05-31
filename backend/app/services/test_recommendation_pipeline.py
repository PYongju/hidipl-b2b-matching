from datetime import datetime
from pathlib import Path
from pprint import pprint

from services.parser.schemas import LineItem, LineItemCategory, QuoteDocument
from services.quote_ingestion.factory import create_quote_ingestion_pipeline
from services.quote_ingestion.schemas import QuoteIngestionResult
from services.ranking.rule_based_ranking_provider import RuleBasedRankingProvider
from services.ranking.schemas import PartnerProfile
from services.recommendation.factory import create_recommendation_pipeline
from services.recommendation.recommendation_pipeline import RecommendationPipeline
from services.recommendation.schemas import RecommendationPipelineResult
from services.requirement.schemas import RequirementInfo
from services.requirement_ingestion.factory import (
    create_requirement_ingestion_pipeline,
)
from services.requirement_ingestion.schemas import RequirementIngestionResult
from services.similarity.factory import create_similarity_provider


REQUIREMENT_TEXT = """신규 프로젝트 연결드립니다. 가능하시면 월요일 오전까지 검토해주시면 좋을 것 같습니다.

1. 수수료모델 A(5%)
2. 고객사: 스노우스페이스
3. 견적 요청 내용: 커브드 LED전광판 + 평면 LED전광판
(1) 커브드 LED 전광판
- 사이즈 : 12,000 × 3,000
- Pitch : 2.5 이하
(2) 플랫 LED전광판
- 사이즈 : 7,150 × 2,700
- Pitch : 2.5 이하
4. 설치 일정: 2월말~3월초
5. 지역: 서울 홍대(동교동)
6. 기타 사항
- 현재 설계 완료 후 건축 시공 진행 중"""


def main() -> None:
    run_offline_unit_test()
    run_azure_integration_test()


def run_offline_unit_test() -> None:
    print("\n========== Recommendation Offline Unit Test ==========")
    requirement_result = _build_requirement_ingestion_result()
    quote_results = [
        _build_quote_ingestion_result(
            quote_id="quote_guide",
            vendor_name="㈜가이드삼정",
            total_supply_price=80000000,
            embedding_vector=[0.95, 0.05, 0.0],
            categories=[
                LineItemCategory.DISPLAY,
                LineItemCategory.DISPLAY,
                LineItemCategory.INSTALL,
            ],
        ),
        _build_quote_ingestion_result(
            quote_id="quote_general",
            vendor_name="일반LED파트너",
            total_supply_price=79000000,
            embedding_vector=[0.98, 0.02, 0.0],
            categories=[LineItemCategory.DISPLAY, LineItemCategory.INSTALL],
        ),
        _build_quote_ingestion_result(
            quote_id="quote_projector",
            vendor_name="프로젝터업체",
            total_supply_price=79000000,
            embedding_vector=[0.0, 1.0, 0.0],
            categories=[LineItemCategory.ETC],
        ),
        _build_quote_ingestion_result(
            quote_id="quote_excluded",
            vendor_name="제외업체",
            total_supply_price=79000000,
            embedding_vector=[0.9, 0.1, 0.0],
            categories=[LineItemCategory.DISPLAY],
        ),
    ]

    ranking_provider = RuleBasedRankingProvider(
        similarity_provider=create_similarity_provider("cosine"),
        partner_profiles=_build_partner_fixtures(),
    )
    pipeline = RecommendationPipeline(ranking_provider=ranking_provider)
    result = pipeline.recommend(
        requirement_result=requirement_result,
        quote_results=quote_results,
        top_n=3,
    )

    _print_recommendation_result(result)
    storage_dict = pipeline.to_storage_dict(result)
    print("\nStorage dict keys:")
    pprint(list(storage_dict.keys()))


def run_azure_integration_test() -> None:
    print("\n========== Recommendation Azure Integration Test ==========")

    try:
        requirement_pipeline = create_requirement_ingestion_pipeline()
        requirement_result = requirement_pipeline.process_text(
            REQUIREMENT_TEXT,
            request_id="integration_test_request",
        )
    except Exception as e:
        print(f"Requirement ingestion 실패로 integration test를 중단합니다: {e}")
        return

    file_paths = sorted(Path("data").glob("*.pdf")) + sorted(Path("data").glob("*.xlsx"))
    if not file_paths:
        file_paths = sorted(Path("samples/quotes").glob("*.pdf"))

    if not file_paths:
        print("Azure integration test용 견적서 파일이 없습니다.")
        return

    try:
        quote_pipeline = create_quote_ingestion_pipeline()
        batch_result = quote_pipeline.process_files(
            file_paths,
            request_id=requirement_result.request_id or "integration_test_request",
        )
    except Exception as e:
        print(f"Quote ingestion pipeline 실행 실패: {e}")
        return

    if not batch_result.results:
        print("추천에 사용할 견적서 ingestion 결과가 없습니다.")
        print("quote ingestion failed_files:")
        pprint(batch_result.failed_files)
        return

    try:
        recommendation_pipeline = create_recommendation_pipeline("rule")
        result = recommendation_pipeline.recommend(
            requirement_result=requirement_result,
            quote_results=batch_result.results,
            top_n=3,
        )
    except Exception as e:
        print(f"Recommendation pipeline 실행 실패: {e}")
        print("quote ingestion failed_files:")
        pprint(batch_result.failed_files)
        return

    print(f"customer_name: {requirement_result.requirement.customer_name}")
    print(f"requirement_embedding_dim: {requirement_result.embedding_dim}")
    print(f"처리한 견적서 수: {len(batch_result.results)}")
    print(f"Top 추천 수: {len(result.items)}")
    print(f"필터된 후보 수: {len(result.filtered_candidates)}")
    print("quote ingestion failed_files:")
    pprint(batch_result.failed_files)

    if not result.items:
        print("파트너 마스터 매칭 실패로 추천 후보 없음")

    _print_recommendation_result(result)


def _build_partner_fixtures() -> list[PartnerProfile]:
    return [
        PartnerProfile(
            name="가이드삼정",
            specialty_tags=["LED 전광판", "커브드", "설치"],
            is_premium=True,
            success_rate=0.10,
            response_speed="fast",
            financial_status="normal",
            is_excluded=False,
        ),
        PartnerProfile(
            name="일반LED파트너",
            specialty_tags=["LED 전광판", "설치"],
            is_premium=False,
            success_rate=0.04,
            response_speed="normal",
            financial_status="normal",
            is_excluded=False,
        ),
        PartnerProfile(
            name="프로젝터업체",
            specialty_tags=["프로젝터"],
            is_premium=False,
            success_rate=0.03,
            response_speed="fast",
            financial_status="normal",
            is_excluded=False,
        ),
        PartnerProfile(
            name="제외업체",
            specialty_tags=["LED 전광판"],
            is_premium=False,
            success_rate=0.0,
            response_speed="slow",
            financial_status="caution",
            is_excluded=True,
        ),
    ]


def _build_requirement_ingestion_result() -> RequirementIngestionResult:
    requirement = RequirementInfo(
        raw_text="커브드 LED 전광판 설치",
        customer_name="스노우스페이스",
        request_summary="커브드 LED전광판 + 평면 LED전광판",
        region="서울 홍대(동교동)",
        install_schedule_text="1개월 이내",
        required_keywords=["LED 전광판", "커브드", "평면", "설치"],
    )

    return RequirementIngestionResult(
        request_id="test_request_001",
        source_type="text",
        source_path=None,
        requirement=requirement,
        embedding_text="",
        embedding_vector=[1.0, 0.0, 0.0],
        embedding_dim=3,
        raw_text_preview="",
        parser_warnings=[],
        parser_raw_matches={},
        ingestion_warnings=[],
        metadata={},
    )


def _build_quote_ingestion_result(
    *,
    quote_id: str,
    vendor_name: str,
    total_supply_price: int,
    embedding_vector: list[float],
    categories: list[LineItemCategory],
) -> QuoteIngestionResult:
    quote = QuoteDocument(
        vendor_name=vendor_name,
        quote_id=quote_id,
        received_at=datetime.now(),
        project_name="스노우스페이스 LED 전광판",
        total_supply_price=total_supply_price,
        total_with_vat=round(total_supply_price * 1.1),
        delivery_weeks=4,
        warranty_months=12,
        line_items=[
            LineItem(
                name=f"{category.value} 품목",
                category=category,
                quantity=1,
                unit="식",
                unit_price=None,
                total_price=total_supply_price if index == 0 else 0,
                spec_raw="커브드 LED 전광판 설치",
            )
            for index, category in enumerate(categories)
        ],
    )

    return QuoteIngestionResult(
        quote_id=quote_id,
        request_id="test_request_001",
        source_file_path=f"samples/{quote_id}.pdf",
        quote=quote,
        embedding_text="",
        embedding_vector=embedding_vector,
        embedding_dim=len(embedding_vector),
        ocr_text_preview="",
        parser_warnings=[],
        parser_raw_matches={},
        ingestion_warnings=[],
        metadata={},
    )


def _print_recommendation_result(result: RecommendationPipelineResult) -> None:
    print(f"request_id: {result.request_id}")
    print(f"customer_name: {result.customer_name}")
    print(f"top_n: {result.top_n}")
    print("items:")
    for item in result.items:
        _print_recommendation_item(item)
    print("all_items:")
    for item in result.all_items:
        _print_recommendation_item(item)
    print("failed_candidates:")
    pprint(result.failed_candidates)
    print("filtered_candidates:")
    pprint(result.filtered_candidates)


def _print_recommendation_item(item) -> None:
    print(f"\nrank: {item.rank}")
    print(f"quote_id: {item.quote_id}")
    print(f"vendor_name: {item.vendor_name}")
    print(f"partner_name: {item.partner_name}")
    print(f"business_rule_passed: {item.business_rule_passed}")
    print(f"is_premium: {item.is_premium}")
    print(f"success_rate: {item.success_rate}")
    print(f"response_speed: {item.response_speed}")
    print(f"financial_status: {item.financial_status}")
    print(f"final_score: {item.final_score}")
    print(f"spec_score: {item.spec_score}")
    print(f"price_score: {item.price_score}")
    print(f"cosine_similarity: {item.cosine_similarity}")
    print(f"filter_reasons: {item.filter_reasons}")
    print(f"check_required: {item.check_required}")
    print(f"business_sort_key: {item.business_sort_key}")


if __name__ == "__main__":
    main()
