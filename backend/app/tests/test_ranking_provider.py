from datetime import datetime
from pathlib import Path
from pprint import pprint

from config.paths import DATA_DIR
from services.config import get_settings
from services.embedding.factory import create_embedding_provider
from services.embedding.text_builder import build_requirement_embedding_text
from services.parser.schemas import LineItem, LineItemCategory, QuoteDocument
from services.quote_ingestion.factory import create_quote_ingestion_pipeline
from services.ranking.rule_based_ranking_provider import RuleBasedRankingProvider
from services.ranking.schemas import PartnerProfile, RankingCandidate, RankingResult
from services.requirement.factory import create_requirement_parser_provider
from services.requirement.schemas import RequirementInfo
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
    print("\n========== Ranking Offline Unit Test ==========")

    requirement = RequirementInfo(
        raw_text="커브드 LED 전광판 설치",
        customer_name="스노우스페이스",
        request_summary="커브드 LED전광판 + 평면 LED전광판",
        region="서울 홍대(동교동)",
        install_schedule_text="1개월 이내",
        required_keywords=["LED 전광판", "커브드", "평면", "설치"],
    )
    requirement_embedding_vector = [1.0, 0.0, 0.0]

    candidates = [
        RankingCandidate(
            quote_id="quote_guide",
            quote_document=_build_quote(
                vendor_name="㈜가이드삼정",
                quote_id="quote_guide",
                project_name="스노우스페이스 LED 전광판",
                total_supply_price=80000000,
                delivery_weeks=4,
                warranty_months=12,
                categories=[
                    LineItemCategory.DISPLAY,
                    LineItemCategory.DISPLAY,
                    LineItemCategory.INSTALL,
                ],
            ),
            quote_embedding_vector=[0.95, 0.05, 0.0],
        ),
        RankingCandidate(
            quote_id="quote_general",
            quote_document=_build_quote(
                vendor_name="일반LED파트너",
                quote_id="quote_general",
                project_name="스노우스페이스 LED",
                total_supply_price=79000000,
                delivery_weeks=4,
                warranty_months=12,
                categories=[LineItemCategory.DISPLAY, LineItemCategory.INSTALL],
            ),
            quote_embedding_vector=[0.98, 0.02, 0.0],
        ),
        RankingCandidate(
            quote_id="quote_projector",
            quote_document=_build_quote(
                vendor_name="프로젝터업체",
                quote_id="quote_projector",
                project_name="회의실 프로젝터",
                total_supply_price=79000000,
                delivery_weeks=4,
                warranty_months=12,
                categories=[LineItemCategory.ETC],
            ),
            quote_embedding_vector=[0.0, 1.0, 0.0],
        ),
        RankingCandidate(
            quote_id="quote_excluded",
            quote_document=_build_quote(
                vendor_name="제외업체",
                quote_id="quote_excluded",
                project_name="LED 전광판",
                total_supply_price=79000000,
                delivery_weeks=4,
                warranty_months=12,
                categories=[LineItemCategory.DISPLAY],
            ),
            quote_embedding_vector=[0.9, 0.1, 0.0],
        ),
    ]

    provider = RuleBasedRankingProvider(
        similarity_provider=create_similarity_provider("cosine"),
        partner_profiles=_build_partner_fixtures(),
    )
    summary = provider.rank(
        requirement=requirement,
        requirement_embedding_vector=requirement_embedding_vector,
        candidates=candidates,
        top_n=3,
    )

    print(f"loaded fixture partners: {len(provider.partner_profiles)}")
    print("Top items:")
    for result in summary.results:
        _print_ranking_result(result)

    print("\nAll items:")
    for result in summary.all_results:
        _print_ranking_result(result)


def run_azure_integration_test() -> None:
    print("\n========== Ranking Azure Integration Test ==========")

    try:
        settings = get_settings()
    except Exception as e:
        print(f"Azure 설정을 로드할 수 없어 integration test를 건너뜁니다: {e}")
        return

    requirement_parser = create_requirement_parser_provider("rule")
    parsed_requirement = requirement_parser.parse(REQUIREMENT_TEXT)
    requirement = parsed_requirement.requirement
    requirement_embedding_text = build_requirement_embedding_text(requirement)

    try:
        embedding_provider = create_embedding_provider("azure_openai")
        requirement_embedding_vector = embedding_provider.embed_text(
            requirement_embedding_text
        )
    except Exception as e:
        print(f"요구사항 임베딩 생성 실패로 integration test를 중단합니다: {e}")
        return

    file_paths = sorted(DATA_DIR.glob("*.pdf")) + sorted(DATA_DIR.glob("*.xlsx"))
    if not file_paths:
        file_paths = sorted((DATA_DIR / "sample_files" / "quotes").glob("*.pdf"))

    if not file_paths:
        print("Azure integration test용 견적서 파일이 없습니다.")
        return

    pipeline = create_quote_ingestion_pipeline(settings)
    batch_result = pipeline.process_files(
        file_paths,
        request_id="integration_test_request",
    )

    candidates = [
        RankingCandidate(
            quote_id=result.quote_id or result.quote.quote_id,
            quote_document=result.quote,
            quote_embedding_vector=result.embedding_vector,
            source_file_path=result.source_file_path,
            metadata=result.metadata,
        )
        for result in batch_result.results
    ]

    provider = RuleBasedRankingProvider(
        similarity_provider=create_similarity_provider("cosine"),
    )
    summary = provider.rank(
        requirement=requirement,
        requirement_embedding_vector=requirement_embedding_vector,
        candidates=candidates,
        top_n=3,
    )

    print(f"로드한 partner 수: {len(provider.partner_profiles)}")
    print(f"처리한 견적서 수: {len(batch_result.results)}")
    print(f"Top 추천 수: {len(summary.results)}")
    print(
        "필터된 후보 수: "
        f"{len([result for result in summary.all_results if not result.business_rule_passed])}"
    )
    print("failed_files:")
    pprint(batch_result.failed_files)

    if not summary.results:
        print("파트너 마스터 매칭 실패 또는 업무 룰 필터링으로 추천 후보 없음")

    print("\nAll candidates:")
    for result in summary.all_results:
        _print_ranking_result(result)


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


def _build_quote(
    *,
    vendor_name: str,
    quote_id: str,
    project_name: str,
    total_supply_price: int,
    delivery_weeks: int | None,
    warranty_months: int | None,
    categories: list[LineItemCategory],
) -> QuoteDocument:
    return QuoteDocument(
        vendor_name=vendor_name,
        quote_id=quote_id,
        received_at=datetime.now(),
        project_name=project_name,
        total_supply_price=total_supply_price,
        total_with_vat=round(total_supply_price * 1.1),
        delivery_weeks=delivery_weeks,
        warranty_months=warranty_months,
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


def _print_ranking_result(result: RankingResult) -> None:
    print(f"\nrank: {result.rank}")
    print(f"quote_id: {result.quote_id}")
    print(f"vendor_name: {result.quote_document.vendor_name}")
    print(f"partner_name: {result.partner_name}")
    print(f"business_rule_passed: {result.business_rule_passed}")
    print(f"is_premium: {result.is_premium}")
    print(f"success_rate: {result.success_rate}")
    print(f"response_speed: {result.response_speed}")
    print(f"financial_status: {result.financial_status}")
    print(f"final_score: {result.final_score}")
    print(f"spec_score: {result.spec_score}")
    print(f"price_score: {result.price_score}")
    print(f"cosine_similarity: {result.cosine_similarity}")
    print(f"filter_reasons: {result.filter_reasons}")
    print(f"check_required: {result.check_required}")
    print(f"business_sort_key: {result.business_sort_key}")


if __name__ == "__main__":
    main()
