import os
from dataclasses import asdict
from pprint import pprint

from dotenv import load_dotenv

from services.explanation.factory import create_explanation_provider
from services.recommendation.schemas import RecommendationItem, RecommendationPipelineResult


def build_recommendation_fixture() -> RecommendationPipelineResult:
    items = [
        RecommendationItem(
            rank=1,
            quote_id="quote_guide",
            partner_name="가이드삼정",
            partner_found=True,
            is_premium=True,
            success_rate=0.10,
            response_speed="fast",
            financial_status="normal",
            business_rule_passed=True,
            business_stage="passed",
            filter_reasons=[],
            business_sort_key=[1, 3.0, 1, 0.1, 3, 2, 92.4, 85.0],
            vendor_name="㈜가이드삼정",
            project_name="스노우스페이스 LED 전광판",
            source_file_path="data/스노우스페이스_커브드LED_가이드삼정.xlsx",
            final_score=92.4,
            spec_score=88.5,
            price_score=85.0,
            delivery_score=80.0,
            warranty_score=100.0,
            installation_score=100.0,
            cosine_similarity=0.77,
            total_supply_price=49800000,
            total_with_vat=54780000,
            delivery_weeks=4,
            warranty_months=12,
            line_item_count=51,
            check_required=[],
            score_breakdown={
                "spec_score": 88.5,
                "price_score": 85.0,
                "delivery_score": 80.0,
                "warranty_score": 100.0,
                "installation_score": 100.0,
                "final_score": 92.4,
            },
        ),
        RecommendationItem(
            rank=2,
            quote_id="quote_daol",
            partner_name="다올씨앤씨",
            partner_found=True,
            is_premium=False,
            success_rate=0.04,
            response_speed="normal",
            financial_status="normal",
            business_rule_passed=True,
            business_stage="passed",
            filter_reasons=[],
            business_sort_key=[1, 1.0, 0, 0.04, 2, 2, 88.0, 100.0],
            vendor_name="(주) 다올씨앤씨",
            project_name="일강이앤아이 회의실 디스플레이",
            source_file_path="data/sample.pdf",
            final_score=88.0,
            spec_score=81.0,
            price_score=100.0,
            delivery_score=70.0,
            warranty_score=100.0,
            installation_score=100.0,
            cosine_similarity=0.62,
            total_supply_price=12800000,
            total_with_vat=14080000,
            delivery_weeks=None,
            warranty_months=12,
            line_item_count=4,
            check_required=["요구 납기 정규화 필요"],
            score_breakdown={
                "spec_score": 81.0,
                "price_score": 100.0,
                "delivery_score": 70.0,
                "warranty_score": 100.0,
                "installation_score": 100.0,
                "final_score": 88.0,
            },
        ),
        RecommendationItem(
            rank=3,
            quote_id="quote_general",
            partner_name="일반LED파트너",
            partner_found=True,
            is_premium=False,
            success_rate=0.03,
            response_speed="normal",
            financial_status="normal",
            business_rule_passed=True,
            business_stage="passed",
            filter_reasons=["가격 차이 5% 초과"],
            business_sort_key=[1, 1.0, 0, 0.03, 2, 2, 70.0, 60.0],
            vendor_name="일반LED파트너",
            project_name="스노우스페이스 LED",
            source_file_path=None,
            final_score=70.0,
            spec_score=79.0,
            price_score=60.0,
            delivery_score=50.0,
            warranty_score=50.0,
            installation_score=0.0,
            cosine_similarity=0.58,
            total_supply_price=78000000,
            total_with_vat=85800000,
            delivery_weeks=None,
            warranty_months=None,
            line_item_count=2,
            check_required=["견적 납기 미기재", "보증기간 미기재", "설치 범위 확인 필요"],
            score_breakdown={
                "spec_score": 79.0,
                "price_score": 60.0,
                "delivery_score": 50.0,
                "warranty_score": 50.0,
                "installation_score": 0.0,
                "final_score": 70.0,
            },
        ),
    ]

    return RecommendationPipelineResult(
        request_id="test_request_001",
        customer_name="스노우스페이스",
        top_n=3,
        items=items,
        all_items=items,
        failed_candidates=[],
        filtered_candidates=[],
        metadata={"fixture": "explanation_provider"},
    )


def print_explanation_result(result) -> None:
    print("provider:", result.provider)
    print("overall_summary:")
    print(result.overall_summary)
    print("\nsupplier_explanations:")
    for item in result.supplier_explanations:
        print()
        print("rank:", item.rank)
        print("vendor_name:", item.vendor_name)
        print("card_summary:", item.card_summary)
        print("strengths:")
        pprint(item.strengths)
        print("weaknesses:")
        pprint(item.weaknesses)
        print("check_required:")
        pprint(item.check_required)


def run_template_test() -> None:
    print("\n========== Explanation Template Test ==========")
    recommendation_result = build_recommendation_fixture()
    provider = create_explanation_provider("template")
    result = provider.generate(recommendation_result)

    print_explanation_result(result)

    storage_dict = asdict(result)
    print("\nStorage dict keys:")
    pprint(list(storage_dict.keys()))


def run_azure_integration_test() -> None:
    print("\n========== Explanation Azure Integration Test ==========")
    load_dotenv()

    missing = [
        name
        for name in [
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_CHAT_DEPLOYMENT",
        ]
        if not os.getenv(name)
    ]
    if missing:
        print(
            "Azure OpenAI Chat 설정이 없어 integration test를 건너뜁니다: "
            + ", ".join(missing)
        )
        return

    recommendation_result = build_recommendation_fixture()
    try:
        provider = create_explanation_provider("azure_openai")
        result = provider.generate(recommendation_result)
    except Exception as e:
        print(f"Azure integration test 실패: {e}")
        return

    print_explanation_result(result)
    _run_fallback_probe(provider, recommendation_result)


def _run_fallback_probe(provider, recommendation_result: RecommendationPipelineResult) -> None:
    class _FakeMessage:
        content = "not-json"

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeResponse:
        choices = [_FakeChoice()]

    class _FakeCompletions:
        def create(self, **kwargs):
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    original_client = provider.client
    provider.client = _FakeClient()
    try:
        fallback_result = provider.generate(recommendation_result)
        print("\nFallback probe provider:", fallback_result.provider)
        print("Fallback warnings:")
        pprint(fallback_result.warnings)
    finally:
        provider.client = original_client


def main() -> None:
    run_template_test()
    run_azure_integration_test()


if __name__ == "__main__":
    main()
