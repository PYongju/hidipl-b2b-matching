from __future__ import annotations

from unittest.mock import patch

from services.api_demo import routers as demo_routers
from services.api_demo.schemas import ProjectCreateRequest
from services.api_demo.store import ApiDemoStore
from services.recommendation.schemas import RecommendationItem, RecommendationPipelineResult


def test_get_matches_returns_recommendation_without_quote_pool() -> None:
    store = ApiDemoStore(persistence=None)
    with patch.object(demo_routers, "store", store):
        project = demo_routers.create_project(
            ProjectCreateRequest(
                company_name="일강이엔아이",
                location="충북 음성",
                deadline="2026년 3월",
                request_text="",
            )
        )
        result = _recommendation_result()
        match = store.save_match(
            project_id=project["project_id"],
            recommendation_result=result,
            explanation_result=None,
        )

        response = demo_routers.get_matches(project["project_id"])

    assert response["project_id"] == project["project_id"]
    assert response["match_id"] == match.match_id
    assert response["quote_pool"] is None
    assert response["quote_count"] == 0
    assert response["quotes"] == []
    assert response["quote_ingestion_results"] == []
    assert response["uploaded_files"] == []
    assert response["failed_files"] == []
    assert response["metadata"]["quote_pool_available"] is False
    assert response["metadata"]["quote_pool_missing"] is True
    assert response["metadata"]["recommendation_source"] == "match_result_snapshot"
    assert response["recommendation"]["items"]
    assert response["recommendation"]["items"][0]["quote_id"] == "quote_led_1"


def test_get_matches_without_match_keeps_existing_not_found_policy() -> None:
    store = ApiDemoStore(persistence=None)
    with patch.object(demo_routers, "store", store):
        project = demo_routers.create_project(
            ProjectCreateRequest(
                company_name="일강이엔아이",
                location="충북 음성",
                deadline="2026년 3월",
                request_text="",
            )
        )
        try:
            demo_routers.get_matches(project["project_id"])
        except KeyError as exc:
            assert "match" in str(exc)
        else:
            raise AssertionError("get_matches must fail when match result is missing")


def test_get_matches_grouped_result_without_quote_pool() -> None:
    store = ApiDemoStore(persistence=None)
    with patch.object(demo_routers, "store", store):
        project = demo_routers.create_project(
            ProjectCreateRequest(
                company_name="일강이엔아이",
                location="충북 음성",
                deadline="2026년 3월",
                request_text="",
            )
        )
        result = _recommendation_result(
            metadata={
                "grouped_by_product_group": True,
                "group_order": ["LED전광판"],
                "product_group_results": {
                    "LED전광판": _recommendation_result(
                        metadata={
                            "product_group": "LED전광판",
                            "product_group_quote_count": 1,
                        }
                    )
                },
                "product_group_explanations": {},
            }
        )
        store.save_match(
            project_id=project["project_id"],
            recommendation_result=result,
            explanation_result=None,
        )

        response = demo_routers.get_matches(
            project["project_id"],
            product_group="LED전광판",
        )

    assert response["quote_pool"] is None
    assert response["metadata"]["quote_pool_available"] is False
    assert len(response["recommendation_groups"]) == 1
    assert response["recommendation_groups"][0]["product_group"] == "LED전광판"
    assert response["recommendation"]["items"][0]["quote_id"] == "quote_led_1"


def _recommendation_result(
    *,
    metadata: dict | None = None,
) -> RecommendationPipelineResult:
    item = RecommendationItem(
        rank=1,
        quote_id="quote_led_1",
        partner_name="테스트파트너",
        partner_found=True,
        is_premium=False,
        success_rate=0.1,
        response_speed="normal",
        financial_status="normal",
        business_rule_passed=True,
        business_stage="passed",
        filter_reasons=[],
        business_sort_key=[],
        vendor_name="테스트파트너",
        project_name="LED전광판 견적",
        source_file_path=None,
        final_score=90.0,
        spec_score=90.0,
        price_score=90.0,
        delivery_score=90.0,
        warranty_score=90.0,
        installation_score=90.0,
        cosine_similarity=0.9,
        total_supply_price=1000000,
        total_with_vat=1100000,
        delivery_weeks=4,
        delivery_basis_raw="4주",
        warranty_months=12,
        line_item_count=1,
        check_required=[],
        score_breakdown={"spec": 90.0},
        metadata={"product_group": "LED전광판"},
    )
    return RecommendationPipelineResult(
        request_id="request_test",
        customer_name="일강이엔아이",
        top_n=3,
        items=[item],
        all_items=[item],
        failed_candidates=[],
        filtered_candidates=[],
        metadata=metadata or {},
    )


def main() -> None:
    test_get_matches_returns_recommendation_without_quote_pool()
    test_get_matches_without_match_keeps_existing_not_found_policy()
    test_get_matches_grouped_result_without_quote_pool()
    print("get matches without quote pool tests passed")


if __name__ == "__main__":
    main()
