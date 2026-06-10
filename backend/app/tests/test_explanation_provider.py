import json
import os
import re
from dataclasses import asdict
from pprint import pprint

from dotenv import load_dotenv

from services.explanation.azure_openai_explanation_provider import (
    AzureOpenAIExplanationProvider,
)
from services.explanation.factory import create_explanation_provider
from services.recommendation.schemas import RecommendationItem, RecommendationPipelineResult


PARSER_PROJECT_FALLBACK = "프로젝트명이 문서에서 명확히 추출되지 않아 파일명 기준으로 보정됨"


def build_recommendation_fixture() -> RecommendationPipelineResult:
    items = [
        RecommendationItem(
            rank=1,
            quote_id="quote_a",
            partner_name="다올씨앤씨",
            partner_found=True,
            is_premium=False,
            success_rate=0.04,
            response_speed="normal",
            financial_status="normal",
            business_rule_passed=True,
            business_stage="passed",
            filter_reasons=[],
            business_sort_key=[1],
            vendor_name="다올씨앤씨",
            project_name="회의실 디스플레이",
            source_file_path=None,
            final_score=91.43,
            spec_score=82.0,
            price_score=100.0,
            delivery_score=100.0,
            warranty_score=100.0,
            installation_score=100.0,
            cosine_similarity=0.8,
            total_supply_price=9440000,
            total_with_vat=10384000,
            delivery_weeks=None,
            delivery_basis_raw="",
            warranty_months=12,
            line_item_count=3,
            check_required=["납기 정보 미기재", PARSER_PROJECT_FALLBACK],
            score_breakdown={},
        ),
        RecommendationItem(
            rank=2,
            quote_id="quote_b",
            partner_name="딥사이닝",
            partner_found=True,
            is_premium=False,
            success_rate=0.04,
            response_speed="normal",
            financial_status="normal",
            business_rule_passed=True,
            business_stage="passed",
            filter_reasons=[],
            business_sort_key=[2],
            vendor_name="딥사이닝",
            project_name="회의실 디스플레이",
            source_file_path=None,
            final_score=78.89,
            spec_score=80.0,
            price_score=70.0,
            delivery_score=90.0,
            warranty_score=100.0,
            installation_score=100.0,
            cosine_similarity=0.7,
            total_supply_price=20300000,
            total_with_vat=22330000,
            delivery_weeks=9,
            delivery_basis_raw="발주 후 60일",
            warranty_months=12,
            line_item_count=5,
            check_required=[PARSER_PROJECT_FALLBACK],
            score_breakdown={},
            comparison_risks=["최저가 대비 가격 차이 5% 초과"],
        ),
        RecommendationItem(
            rank=3,
            quote_id="quote_c",
            partner_name="효성ITX",
            partner_found=True,
            is_premium=True,
            success_rate=0.2,
            response_speed="normal",
            financial_status="normal",
            business_rule_passed=True,
            business_stage="passed",
            filter_reasons=[],
            business_sort_key=[3],
            vendor_name="효성ITX",
            project_name="회의실 디스플레이",
            source_file_path=None,
            final_score=70.0,
            spec_score=78.0,
            price_score=60.0,
            delivery_score=60.0,
            warranty_score=100.0,
            installation_score=70.0,
            cosine_similarity=0.6,
            total_supply_price=14473000,
            total_with_vat=15920300,
            delivery_weeks=None,
            delivery_basis_raw="별도협의",
            warranty_months=12,
            line_item_count=4,
            check_required=[
                "공급가+VAT와 견적서 총액이 44,000원 차이납니다. 만원 단위 절사 또는 조정금액 가능성 확인 필요",
                "설치 범위 확인 필요",
            ],
            score_breakdown={},
        ),
    ]
    return RecommendationPipelineResult(
        request_id="test_request_001",
        customer_name="일강이앤아이",
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


def llm_payload(suppliers, overall_summary: str = "Top3 견적을 비교한 요약입니다.") -> str:
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


def _assert_parser_quality_filtered(result) -> None:
    text = result.overall_summary + " " + " ".join(
        weakness
        for supplier in result.supplier_explanations
        for weakness in supplier.weaknesses
    )
    assert "프로젝트명" not in text
    assert "파일명 기준" not in text
    assert PARSER_PROJECT_FALLBACK in result.supplier_explanations[0].check_required
    assert not any(
        "가격 차이 5% 초과" in check
        for supplier in result.supplier_explanations
        for check in supplier.check_required
    )


def _assert_output_lengths(result) -> None:
    sentence_count = len(
        [
            s
            for s in re.split(r"(?<=[.!?])\s+", result.overall_summary)
            if s.strip()
        ]
    )
    assert 1 <= sentence_count <= 3, result.overall_summary
    for supplier in result.supplier_explanations:
        assert len(supplier.strengths) <= 2
        assert len(supplier.weaknesses) <= 2
        assert "\n" not in supplier.card_summary
        if "납기 정보 미기재" in supplier.check_required or "납기 별도협의" in supplier.check_required:
            delivery_text = supplier.card_summary + " " + " ".join(supplier.strengths)
            assert not (
                "납기" in delivery_text
                and any(token in delivery_text for token in ["우수", "최고", "명확"])
            )


def run_template_test() -> None:
    print("\n========== Explanation Template Test ==========")
    recommendation_result = build_recommendation_fixture()
    provider = create_explanation_provider("template")
    result = provider.generate(recommendation_result)

    print_explanation_result(result)
    _assert_parser_quality_filtered(result)
    _assert_output_lengths(result)
    assert "납기 정보 미기재" in result.supplier_explanations[0].weaknesses
    assert "가격 차이 5% 초과" in result.supplier_explanations[1].weaknesses
    assert not any(
        "납기 우수" in strength or "납기 명확" in strength
        for strength in result.supplier_explanations[0].strengths
    )

    storage_dict = asdict(result)
    print("\nStorage dict keys:")
    pprint(list(storage_dict.keys()))


def run_azure_unit_tests() -> None:
    print("\n========== Explanation Azure Unit Tests ==========")
    recommendation_result = build_recommendation_fixture()
    expected = ["quote_a", "quote_b", "quote_c"]

    duplicate_result = make_provider_with_response(
        llm_payload(
            [
                {"quote_id": "quote_a", "card_summary": "A1", "strengths": ["최종 점수 우수"], "weaknesses": []},
                {"quote_id": "quote_a", "card_summary": "A2", "strengths": ["중복"], "weaknesses": []},
                {"quote_id": "quote_b", "card_summary": "B", "strengths": ["납기 명확"], "weaknesses": []},
            ]
        )
    ).generate(recommendation_result)
    assert_quote_order(duplicate_result, expected)
    assert duplicate_result.metadata["duplicate_quote_ids"] == ["quote_a"]
    assert duplicate_result.supplier_explanations[2].metadata["fallback_used"] is True

    shuffled_result = make_provider_with_response(
        llm_payload(
            [
                {"quote_id": "quote_b", "card_summary": "B", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_a", "card_summary": "A", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_c", "card_summary": "C", "strengths": [], "weaknesses": []},
            ]
        )
    ).generate(recommendation_result)
    assert_quote_order(shuffled_result, expected)
    assert [item.rank for item in shuffled_result.supplier_explanations] == [1, 2, 3]

    unknown_result = make_provider_with_response(
        llm_payload(
            [
                {"quote_id": "quote_a", "card_summary": "A", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_b", "card_summary": "B", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_unknown", "card_summary": "X", "strengths": [], "weaknesses": []},
            ]
        )
    ).generate(recommendation_result)
    assert_quote_order(unknown_result, expected)
    assert unknown_result.metadata["unknown_quote_ids"] == ["quote_unknown"]
    assert unknown_result.supplier_explanations[2].metadata["fallback_used"] is True

    duplicate_weakness_result = make_provider_with_response(
        llm_payload(
            [
                {
                    "quote_id": "quote_a",
                    "card_summary": "파일명 기준으로 보정된 견적입니다.",
                    "strengths": ["납기 우수", "가격 점수 우수"],
                    "weaknesses": ["납기 정보가 미기재되어 추가 확인 필요"],
                },
                {"quote_id": "quote_b", "card_summary": "B", "strengths": [], "weaknesses": []},
                {"quote_id": "quote_c", "card_summary": "C", "strengths": [], "weaknesses": []},
            ],
            overall_summary="프로젝트명이 파일명 기준으로 보정되어 확인이 필요합니다.",
        )
    ).generate(recommendation_result)
    first = duplicate_weakness_result.supplier_explanations[0]
    assert first.weaknesses.count("납기 정보 미기재") == 1
    assert not any("납기 우수" in strength for strength in first.strengths)
    _assert_parser_quality_filtered(duplicate_weakness_result)
    _assert_output_lengths(duplicate_weakness_result)

    metadata_result = duplicate_weakness_result.supplier_explanations[0].metadata
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

    provider = make_provider_with_response(llm_payload([]), max_tokens=2222)
    max_token_result = provider.generate(recommendation_result)
    assert provider.client.chat.completions.last_kwargs["max_tokens"] == 2222
    assert max_token_result.metadata["max_tokens"] == 2222
    user_payload = provider.client.chat.completions.last_kwargs["messages"][1]["content"]
    assert '"comparison_risks"' in user_payload
    assert '"parser_quality_notes"' not in user_payload
    assert "가격 차이 5% 초과" in provider._system_prompt()

    print("Azure unit tests passed")


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
        print("Azure OpenAI Chat 설정 없음: integration test skip - " + ", ".join(missing))
        return

    recommendation_result = build_recommendation_fixture()
    try:
        provider = create_explanation_provider("azure_openai")
        result = provider.generate(recommendation_result)
    except Exception as e:
        print(f"Azure integration test failed: {e}")
        return

    print_explanation_result(result)
    _assert_parser_quality_filtered(result)


def main() -> None:
    run_template_test()
    run_azure_unit_tests()
    run_azure_integration_test()


if __name__ == "__main__":
    main()
