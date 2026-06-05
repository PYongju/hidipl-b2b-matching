import os
from dataclasses import asdict
from pprint import pprint

from dotenv import load_dotenv

from config.paths import DATA_DIR
from services.explanation.factory import create_explanation_provider
from services.explanation.azure_openai_explanation_provider import AzureOpenAIExplanationProvider
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
            source_file_path=str(DATA_DIR / "스노우스페이스_커브드LED_가이드삼정.xlsx"),
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
            delivery_basis_raw="4주",
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
            source_file_path=str(DATA_DIR / "sample.pdf"),
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
            delivery_basis_raw="",
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
            delivery_basis_raw="",
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


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str, finish_reason: str = "stop") -> None:
        self.message = FakeMessage(content)
        self.finish_reason = finish_reason


class FakeResponse:
    def __init__(self, content: str, finish_reason: str = "stop") -> None:
        self.choices = [FakeChoice(content, finish_reason)]


class FakeCompletions:
    def __init__(self, content: str, finish_reason: str = "stop") -> None:
        self.content = content
        self.finish_reason = finish_reason
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeResponse(self.content, self.finish_reason)


class FakeChat:
    def __init__(self, content: str, finish_reason: str = "stop") -> None:
        self.completions = FakeCompletions(content, finish_reason)


class FakeClient:
    def __init__(self, content: str, finish_reason: str = "stop") -> None:
        self.chat = FakeChat(content, finish_reason)


def make_provider_with_response(
    content: str,
    *,
    finish_reason: str = "stop",
    max_tokens: int | None = None,
) -> AzureOpenAIExplanationProvider:
    return AzureOpenAIExplanationProvider(
        endpoint="https://example.openai.azure.com",
        api_key="test-key",
        deployment="test-deployment",
        api_version="2025-01-01-preview",
        client=FakeClient(content, finish_reason),
        max_tokens=max_tokens,
    )


def llm_payload(suppliers, overall_summary: str = "Top 3 공급사를 비교한 요약입니다.") -> str:
    import json

    return json.dumps(
        {
            "overall_summary": overall_summary,
            "supplier_explanations": suppliers,
        },
        ensure_ascii=False,
    )


def assert_quote_order(result, expected):
    actual = [item.quote_id for item in result.supplier_explanations]
    assert actual == expected, actual


def run_azure_unit_tests() -> None:
    print("\n========== Explanation Azure Unit Tests ==========")
    recommendation_result = build_recommendation_fixture()
    expected = ["quote_guide", "quote_daol", "quote_general"]

    duplicate_result = make_provider_with_response(
        llm_payload(
            [
                {"quote_id": "quote_guide", "card_summary": "A1", "strengths": ["s1"], "weaknesses": []},
                {"quote_id": "quote_guide", "card_summary": "A2", "strengths": ["s2"], "weaknesses": []},
                {"quote_id": "quote_daol", "card_summary": "B", "strengths": ["s3"], "weaknesses": []},
            ]
        )
    ).generate(recommendation_result)
    assert_quote_order(duplicate_result, expected)
    assert duplicate_result.metadata["duplicate_quote_ids"] == ["quote_guide"]
    assert duplicate_result.supplier_explanations[2].metadata["fallback_used"] is True

    shuffled_result = make_provider_with_response(
        llm_payload(
            [
                {"quote_id": "quote_daol", "card_summary": "B", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_guide", "card_summary": "A", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_general", "card_summary": "C", "strengths": [], "weaknesses": []},
            ]
        )
    ).generate(recommendation_result)
    assert_quote_order(shuffled_result, expected)
    assert [item.rank for item in shuffled_result.supplier_explanations] == [1, 2, 3]

    missing_result = make_provider_with_response(
        llm_payload(
            [
                {"quote_id": "quote_guide", "card_summary": "A", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_daol", "card_summary": "B", "strengths": [], "weaknesses": []},
            ]
        )
    ).generate(recommendation_result)
    assert_quote_order(missing_result, expected)
    assert missing_result.metadata["missing_quote_ids"] == ["quote_general"]
    assert missing_result.supplier_explanations[2].metadata["fallback_reason"] == "missing_llm_supplier_explanation"

    unknown_result = make_provider_with_response(
        llm_payload(
            [
                {"quote_id": "quote_guide", "card_summary": "A", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_daol", "card_summary": "B", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_unknown", "card_summary": "X", "strengths": [], "weaknesses": []},
            ]
        )
    ).generate(recommendation_result)
    assert_quote_order(unknown_result, expected)
    assert unknown_result.metadata["unknown_quote_ids"] == ["quote_unknown"]
    assert unknown_result.supplier_explanations[2].metadata["fallback_used"] is True

    weaknesses_result = make_provider_with_response(
        llm_payload(
            [
                {"quote_id": "quote_guide", "card_summary": "A", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_daol", "card_summary": "B", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_general", "card_summary": "C", "strengths": [], "weaknesses": []},
            ]
        )
    ).generate(recommendation_result)
    daol = weaknesses_result.supplier_explanations[1]
    assert recommendation_result.items[1].check_required[0] in daol.weaknesses
    assert daol.check_required == recommendation_result.items[1].check_required

    metadata_result = weaknesses_result.supplier_explanations[0].metadata
    for key in [
        "final_score",
        "spec_score",
        "price_score",
        "delivery_score",
        "warranty_score",
        "installation_score",
        "business_rule_passed",
        "filter_reasons",
    ]:
        assert key in metadata_result

    provider = make_provider_with_response(
        llm_payload([]),
        max_tokens=2222,
    )
    max_token_result = provider.generate(recommendation_result)
    assert provider.client.chat.completions.last_kwargs["max_tokens"] == 2222
    assert max_token_result.metadata["max_tokens"] == 2222

    empty_summary_result = make_provider_with_response(
        llm_payload(
            [
                {"quote_id": "quote_guide", "card_summary": "A", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_daol", "card_summary": "B", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_general", "card_summary": "C", "strengths": [], "weaknesses": []},
            ],
            overall_summary="",
        )
    ).generate(recommendation_result)
    assert empty_summary_result.overall_summary
    assert any("template summary used" in warning for warning in empty_summary_result.warnings)

    print("Azure unit tests passed")


def main() -> None:
    run_template_test()
    run_azure_unit_tests()
    run_azure_integration_test()


if __name__ == "__main__":
    main()
