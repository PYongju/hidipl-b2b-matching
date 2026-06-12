from __future__ import annotations

from datetime import datetime

from services.parser.schemas import LineItem, LineItemCategory, QuoteDocument
from services.quote_ingestion.schemas import QuoteIngestionResult
from services.recommendation.product_group_filter import (
    filter_quotes_by_product_group_scope,
    infer_dominant_quote_product_groups,
    resolve_quote_product_groups,
    resolve_requirement_product_groups,
)
from services.requirement.schemas import RequirementInfo, RequirementProduct


def main() -> None:
    test_requirement_led_filters_video_split_option()
    test_requirement_video_filters_led_split_option()
    test_requirement_led_and_video_includes_both()
    test_dominant_video_group_filters_led_split_option()
    test_quote_pool_dominant_video_wall_excludes_hyosung_led_option()
    test_ambiguous_group_keeps_all_quotes()
    test_uncertain_quote_is_included()
    test_candidate_vendor_selection_is_not_used()
    print("product group filter tests passed")


def test_requirement_led_filters_video_split_option() -> None:
    led, video = build_split_hyosung_quotes()
    requirement = requirement_for("LED전광판")

    included, excluded, metadata = filter_quotes_by_product_group_scope(requirement, [led, video])

    assert [item.quote_id for item in included] == [led.quote_id]
    assert excluded[0]["quote_id"] == video.quote_id
    assert excluded[0]["reason"] == "고객 요구사항의 비교 제품군과 불일치"
    assert metadata["source"] == "requirement"
    assert metadata["selected_product_groups"] == ["LED전광판"]
    assert metadata["excluded_quote_count"] == 1


def test_requirement_video_filters_led_split_option() -> None:
    led, video = build_split_hyosung_quotes()
    requirement = requirement_for("비디오월")

    included, excluded, metadata = filter_quotes_by_product_group_scope(requirement, [led, video])

    assert [item.quote_id for item in included] == [video.quote_id]
    assert excluded[0]["quote_id"] == led.quote_id
    assert metadata["selected_product_groups"] == ["비디오월"]
    assert metadata["excluded_quote_count"] == 1


def test_requirement_led_and_video_includes_both() -> None:
    led, video = build_split_hyosung_quotes()
    requirement = RequirementInfo(
        raw_text="LED전광판과 비디오월 모두 비교",
        products=[
            RequirementProduct(product_type="LED전광판", raw_text="LED전광판"),
            RequirementProduct(product_type="비디오월", raw_text="비디오월"),
        ],
    )

    included, excluded, metadata = filter_quotes_by_product_group_scope(requirement, [led, video])

    assert {item.quote_id for item in included} == {led.quote_id, video.quote_id}
    assert excluded == []
    assert metadata["selected_product_groups"] == ["LED전광판", "비디오월"]
    assert metadata["excluded_quote_count"] == 0


def test_dominant_video_group_filters_led_split_option() -> None:
    led, video = build_split_hyosung_quotes()
    video_quotes = [
        quote_result("daol_video", "다올씨앤씨", "46인치 비디오월", "비디오월"),
        quote_result("deep_video", "딥사이닝", "55인치 비디오월", "비디오월"),
        quote_result("sys_video", "시스메이트", "비디오월 3x3", "비디오월"),
        video,
        led,
    ]
    requirement = ambiguous_display_requirement()

    included, excluded, metadata = filter_quotes_by_product_group_scope(requirement, video_quotes)

    assert resolve_requirement_product_groups(requirement) == set()
    assert metadata["source"] == "quote_pool_dominant_group"
    assert metadata["selected_product_groups"] == ["비디오월"]
    assert led.quote_id not in {item.quote_id for item in included}
    assert video.quote_id in {item.quote_id for item in included}
    assert len(excluded) == 1
    assert excluded[0]["quote_id"] == led.quote_id
    assert excluded[0]["reason"] == "동일 PDF 내 복수 제품군 옵션 중 비교 scope와 다른 제품군"


def test_quote_pool_dominant_video_wall_excludes_hyosung_led_option() -> None:
    led, video = build_split_hyosung_quotes()
    quote_documents = [
        video,
        led,
        quote_result("daol_46_video", "다올씨앤씨", "일강_비디오월_46인치", "비디오월"),
        quote_result("deep_49_video", "딥사이닝", "일강_비디오월_49인치", "비디오월"),
        quote_result("sys_55_video", "시스메이트", "일강_비디오월_55인치", "비디오월"),
    ]
    requirement = ambiguous_display_requirement()

    included, excluded, metadata = filter_quotes_by_product_group_scope(
        requirement=requirement,
        quote_documents=quote_documents,
    )

    included_ids = {quote.quote_id for quote in included}
    excluded_ids = {candidate["quote_id"] for candidate in excluded}
    assert resolve_requirement_product_groups(requirement) == set()
    assert metadata["source"] == "quote_pool_dominant_group"
    assert metadata["selected_product_groups"] == ["비디오월"]
    assert metadata["quote_product_group_counts"]["비디오월"] > metadata["quote_product_group_counts"]["LED전광판"]
    assert video.quote_id in included_ids
    assert led.quote_id in excluded_ids
    assert any(quote.quote.vendor_name == "효성ITX" and "비디오월" in quote.quote_id for quote in included)
    assert any(candidate["vendor_name"] == "효성ITX" and "LED전광판" in candidate["quote_id"] for candidate in excluded)
    assert metadata["excluded_quote_count"] == 1
    assert metadata["selection_required"] is False


def test_ambiguous_group_keeps_all_quotes() -> None:
    quotes = [
        quote_result("led", "LED업체", "LED전광판", "LED전광판"),
        quote_result("video", "비디오월업체", "비디오월", "비디오월"),
    ]
    requirement = RequirementInfo(raw_text="디스플레이 비교")

    included, excluded, metadata = filter_quotes_by_product_group_scope(requirement, quotes)

    assert [item.quote_id for item in included] == ["led", "video"]
    assert excluded == []
    assert metadata["enabled"] is False
    assert metadata["selection_required"] is True
    assert metadata["reason"] == "비교 제품군을 자동 결정할 수 없음"


def test_uncertain_quote_is_included() -> None:
    led = quote_result("led", "LED업체", "LED전광판", "LED전광판")
    uncertain = quote_result("unknown", "미확정업체", "회의실 디스플레이", None)
    requirement = requirement_for("LED전광판")

    included, excluded, metadata = filter_quotes_by_product_group_scope(
        requirement,
        [led, uncertain],
    )

    assert {item.quote_id for item in included} == {"led", "unknown"}
    assert excluded == []
    assert metadata["uncertain_quote_ids"] == ["unknown"]


def test_candidate_vendor_selection_is_not_used() -> None:
    candidate_selected_video = quote_result(
        "candidate_video",
        "추천업체",
        "비디오월",
        "비디오월",
        candidate_selected=True,
    )
    non_candidate_led = quote_result(
        "non_candidate_led",
        "비추천업체",
        "LED전광판",
        "LED전광판",
        candidate_selected=False,
    )
    requirement = requirement_for("LED전광판")

    included, excluded, metadata = filter_quotes_by_product_group_scope(
        requirement,
        [candidate_selected_video, non_candidate_led],
    )

    assert [item.quote_id for item in included] == ["non_candidate_led"]
    assert excluded[0]["quote_id"] == "candidate_video"
    assert metadata["source"] == "requirement"


def requirement_for(product_group: str) -> RequirementInfo:
    return RequirementInfo(
        raw_text=f"{product_group} 설치 요청",
        category=product_group,
        products=[RequirementProduct(product_type=product_group, raw_text=product_group)],
        required_keywords=[product_group],
        metadata={"frontend_fields": {"카테고리": product_group}},
    )


def ambiguous_display_requirement() -> RequirementInfo:
    return RequirementInfo(
        raw_text="회의실 디스플레이 설치 검토",
        customer_name="일강이앤아이",
        project_name="충북 음성 회의실 디스플레이",
        request_summary="회의실 디스플레이 설치 검토",
        region="충북 음성",
        install_schedule_text="2026년 3월",
        project_stage="실시설계 단계",
        products=[],
        required_keywords=["디스플레이", "회의실", "설치"],
        metadata={
            "source": "test_ambiguous_product_group",
            "frontend_fields": {
                "카테고리": "디스플레이",
                "디스플레이 크기": "미입력",
                "추가 요청사항": "회의실용 디스플레이 설치",
            },
        },
    )


def build_split_hyosung_quotes() -> tuple[QuoteIngestionResult, QuoteIngestionResult]:
    parent_id = "hyosung_parent"
    led = quote_result(
        f"{parent_id}_opt1_LED전광판",
        "효성ITX",
        "충북 음성 회의실 디스플레이 - LED전광판",
        "LED전광판",
        parent_quote_id=parent_id,
        option_index=1,
    )
    video = quote_result(
        f"{parent_id}_opt2_비디오월",
        "효성ITX",
        "충북 음성 회의실 디스플레이 - 비디오월",
        "비디오월",
        parent_quote_id=parent_id,
        option_index=2,
    )
    return led, video


def quote_result(
    quote_id: str,
    vendor_name: str,
    project_name: str,
    product_group: str | None,
    *,
    parent_quote_id: str | None = None,
    option_index: int | None = None,
    candidate_selected: bool | None = None,
) -> QuoteIngestionResult:
    line_item_name = product_group or "회의실 디스플레이"
    quote = QuoteDocument(
        vendor_name=vendor_name,
        quote_id=quote_id,
        received_at=datetime(2026, 6, 12),
        project_name=project_name,
        total_supply_price=1_000_000,
        total_with_vat=1_100_000,
        line_items=[
            LineItem(
                name=line_item_name,
                category=LineItemCategory.DISPLAY,
                quantity=1.0,
                unit="식",
                unit_price=1_000_000,
                total_price=1_000_000,
                spec_raw=line_item_name,
            )
        ],
    )
    metadata = {}
    parser_raw_matches = {}
    if parent_quote_id:
        metadata.update(
            {
                "split_from_multi_option": True,
                "parent_quote_id": parent_quote_id,
                "option_index": option_index,
                "option_label": product_group,
            }
        )
        parser_raw_matches = {
            "multi_option_split": {
                "split_from_multi_option": True,
                "parent_quote_id": parent_quote_id,
                "option_index": option_index,
                "option_label": product_group,
            },
            "multi_option_detection": {
                "product_groups": ["LED전광판", "비디오월"],
                "auto_split": True,
            },
        }
    if candidate_selected is not None:
        metadata["candidate_vendor_link"] = {
            "candidate_vendor_matching_executed": True,
            "is_selected_vendor": candidate_selected,
            "matched_vendor_name": vendor_name if candidate_selected else None,
        }
    return QuoteIngestionResult(
        quote_id=quote_id,
        request_id="test",
        source_file_path="",
        quote=quote,
        embedding_text="",
        embedding_vector=None,
        embedding_dim=None,
        ocr_text_preview="",
        parser_warnings=[],
        parser_raw_matches=parser_raw_matches,
        ingestion_warnings=[],
        metadata=metadata,
    )


if __name__ == "__main__":
    main()
