from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

from services.api_demo.store import ApiDemoStore
from services.api_demo.store_persistence import (
    FakeJsonApiDemoPersistence,
    SqlJsonApiDemoPersistence,
)
from services.api_demo.store_serialization import (
    deserialize_candidate_vendor_record,
    deserialize_match_record,
    deserialize_project_record,
    deserialize_quote_pool_record,
    sanitize_for_api_output,
    serialize_candidate_vendor_record,
    serialize_match_record,
    serialize_project_record,
    serialize_quote_pool_record,
)
from services.explanation.schemas import RecommendationExplanationResult, SupplierExplanation
from services.parser.schemas import LineItem, LineItemCategory, QuoteDocument
from services.partner_matching.schemas import PartnerMatchCandidate, PartnerMatchingResult
from services.quote_ingestion.schemas import QuoteIngestionResult
from services.recommendation.schemas import RecommendationItem, RecommendationPipelineResult
from services.requirement.schemas import RequirementInfo, RequirementProduct
from services.requirement_ingestion.schemas import RequirementIngestionResult


def main() -> None:
    test_store_record_serialization_roundtrip()
    test_in_memory_fallback_without_persistence()
    test_fake_persistence_restart_simulation()
    test_requested_vendor_ids_restore_and_memory_update()
    test_candidate_vendor_row_requested_vendor_ids_fallback()
    print("API demo store persistence tests passed")


def test_store_record_serialization_roundtrip() -> None:
    store = ApiDemoStore()
    records = _populate_store(store)

    project_data = serialize_project_record(records["project"])
    quote_pool_data = serialize_quote_pool_record(records["quote_pool"])
    match_data = serialize_match_record(records["match"])
    candidate_data = serialize_candidate_vendor_record(records["candidate_vendors"])

    assert project_data["requirement_result"]["embedding_vector"] == [0.1, 0.2, 0.3]
    assert "api_key" not in json.dumps(project_data, ensure_ascii=False).lower()
    assert "endpoint" not in json.dumps(project_data, ensure_ascii=False).lower()
    assert "ocr_full_text" not in json.dumps(quote_pool_data, ensure_ascii=False)

    restored_project = deserialize_project_record(project_data)
    restored_quote_pool = deserialize_quote_pool_record(quote_pool_data)
    restored_match = deserialize_match_record(match_data)
    restored_candidate = deserialize_candidate_vendor_record(candidate_data)

    assert restored_project.project_id == records["project"].project_id
    assert restored_project.requirement_result.requirement.customer_name == "일강이앤아이"
    assert restored_project.requirement_result.embedding_vector == [0.1, 0.2, 0.3]
    assert restored_quote_pool.quote_ingestion_results[0].quote.vendor_name == "효성ITX"
    assert restored_match.recommendation_result.items[0].quote_id == "quote_001"
    assert restored_candidate.candidate_vendor_result.candidates[0].partner_name == "효성ITX"

    api_safe = sanitize_for_api_output(project_data)
    api_safe_text = json.dumps(api_safe, ensure_ascii=False)
    assert "embedding_vector" not in api_safe_text
    assert "api_key" not in api_safe_text.lower()
    assert "endpoint" not in api_safe_text.lower()


def test_in_memory_fallback_without_persistence() -> None:
    store = ApiDemoStore(persistence=None)
    records = _populate_store(store)

    assert store.get_project(records["project"].project_id) is records["project"]
    assert store.get_quote_pool(records["project"].project_id) is records["quote_pool"]
    assert store.get_latest_match(records["project"].project_id) is records["match"]
    assert store.get_candidate_vendors(records["project"].project_id) is records["candidate_vendors"]


def test_fake_persistence_restart_simulation() -> None:
    persistence = FakeJsonApiDemoPersistence()
    store1 = ApiDemoStore(persistence=persistence)
    records = _populate_store(store1)
    project_id = records["project"].project_id
    match_id = records["match"].match_id

    store2 = ApiDemoStore(persistence=persistence)

    restored_project = store2.get_project(project_id)
    restored_quote_pool = store2.get_quote_pool(project_id)
    restored_match = store2.get_match(project_id, match_id)
    restored_latest_match = store2.get_latest_match(project_id)
    restored_candidate_vendors = store2.get_candidate_vendors(project_id)

    assert restored_project is not None
    assert restored_quote_pool is not None
    assert restored_match is not None
    assert restored_latest_match is not None
    assert restored_candidate_vendors is not None
    assert restored_project.requirement_result.requirement.project_name == "회의실 디스플레이"
    assert restored_quote_pool.quote_ingestion_results[0].quote.line_items[0].name == "LED Display"
    assert restored_match.recommendation_result.items[0].vendor_name == "효성ITX"
    assert restored_latest_match.match_id == match_id
    assert restored_candidate_vendors.selected_vendor_names == ["효성ITX"]

    explanation = RecommendationExplanationResult(
        request_id="request_test",
        customer_name="일강이앤아이",
        overall_summary="효성ITX가 종합 1순위입니다.",
        supplier_explanations=[
            SupplierExplanation(
                quote_id="quote_001",
                vendor_name="효성ITX",
                rank=1,
                card_summary="가격과 사양이 우수합니다.",
                strengths=["가격 경쟁력"],
                weaknesses=[],
                check_required=[],
            )
        ],
        provider="template",
        warnings=[],
    )
    store2.update_match_explanation(
        project_id=project_id,
        match_id=match_id,
        explanation_result=explanation,
    )
    store3 = ApiDemoStore(persistence=persistence)
    restored_match_with_explanation = store3.get_match(project_id, match_id)
    assert restored_match_with_explanation is not None
    assert restored_match_with_explanation.explanation_result is not None
    assert restored_match_with_explanation.explanation_result.overall_summary == "효성ITX가 종합 1순위입니다."


def test_requested_vendor_ids_restore_and_memory_update() -> None:
    persistence = FakeJsonApiDemoPersistence()
    store1 = ApiDemoStore(persistence=persistence)
    records = _populate_store(store1)
    project_id = records["project"].project_id
    candidate_record = records["candidate_vendors"]
    candidate_record.requested_vendor_ids = ["vendor_a", "vendor_b"]
    persistence.save_candidate_vendor_record(candidate_record)

    store2 = ApiDemoStore(persistence=persistence)
    restored = store2.get_candidate_vendors(project_id)
    assert restored is not None
    assert restored.requested_vendor_ids == ["vendor_a", "vendor_b"]

    updated = store2.update_candidate_vendor_requested_vendor_ids(
        project_id,
        ["vendor_1", "vendor_2", "vendor_3"],
    )
    assert updated is True
    assert store2.get_candidate_vendors(project_id).requested_vendor_ids == [
        "vendor_1",
        "vendor_2",
        "vendor_3",
    ]


def test_candidate_vendor_row_requested_vendor_ids_fallback() -> None:
    store = ApiDemoStore()
    records = _populate_store(store)
    candidate_data = serialize_candidate_vendor_record(records["candidate_vendors"])
    persistence = SqlJsonApiDemoPersistence(enabled=False)

    row = _candidate_vendor_row(candidate_data, requested_vendor_ids_json='["vendor_a", "vendor_b"]')
    restored = persistence._row_to_candidate_vendor_record(row)
    assert restored is not None
    assert restored.requested_vendor_ids == ["vendor_a", "vendor_b"]

    invalid_row = _candidate_vendor_row(candidate_data, requested_vendor_ids_json="not-json")
    restored_invalid = persistence._row_to_candidate_vendor_record(invalid_row)
    assert restored_invalid is not None
    assert restored_invalid.requested_vendor_ids == []

    null_row = _candidate_vendor_row(candidate_data, requested_vendor_ids_json=None)
    restored_null = persistence._row_to_candidate_vendor_record(null_row)
    assert restored_null is not None
    assert restored_null.requested_vendor_ids == []


def _candidate_vendor_row(
    candidate_data: dict,
    *,
    requested_vendor_ids_json,
) -> SimpleNamespace:
    return SimpleNamespace(
        candidate_vendor_id=candidate_data["candidate_vendor_id"],
        project_id=candidate_data["project_id"],
        requirement_result_json=json.dumps(
            candidate_data["requirement_result"],
            ensure_ascii=False,
        ),
        candidate_vendor_result_json=json.dumps(
            candidate_data["candidate_vendor_result"],
            ensure_ascii=False,
        ),
        selected_vendor_names_json=json.dumps(
            candidate_data["selected_vendor_names"],
            ensure_ascii=False,
        ),
        requested_vendor_names_json=json.dumps(
            candidate_data["requested_vendor_names"],
            ensure_ascii=False,
        ),
        requested_vendor_ids_json=requested_vendor_ids_json,
        top_n=candidate_data["top_n"],
        similarity_threshold=candidate_data["similarity_threshold"],
        executed_at=candidate_data["executed_at"],
        created_at=candidate_data["created_at"],
    )


def _populate_store(store: ApiDemoStore) -> dict[str, object]:
    requirement_result = _build_requirement_result()
    project = store.create_project(
        company_name="일강이앤아이",
        location="충북 음성",
        deadline="2026년 3월",
        request_text="회의실 디스플레이 설치",
        requirement_result=requirement_result,
        original_request_text="회의실 디스플레이 설치",
        requirement_source="frontend_project_payload",
    )
    quote_pool = store.save_quote_pool(
        project_id=project.project_id,
        uploaded_files=["data/sample.pdf"],
        quote_ingestion_results=[_build_quote_ingestion_result(project.request_id)],
        failed_files=[],
    )
    match = store.save_match(
        project_id=project.project_id,
        recommendation_result=_build_recommendation_result(project.request_id),
    )
    candidate_vendors = store.save_candidate_vendors(
        project_id=project.project_id,
        requirement_result=requirement_result,
        candidate_vendor_result=_build_partner_matching_result(project.request_id),
        top_n=10,
        similarity_threshold=60.0,
    )
    return {
        "project": project,
        "quote_pool": quote_pool,
        "match": match,
        "candidate_vendors": candidate_vendors,
    }


def _build_requirement_result() -> RequirementIngestionResult:
    requirement = RequirementInfo(
        raw_text="회의실 디스플레이 설치",
        customer_name="일강이앤아이",
        project_name="회의실 디스플레이",
        request_summary="회의실 LED전광판 설치",
        products=[
            RequirementProduct(
                product_type="LED전광판",
                name="LED Display",
                quantity=1,
                unit="식",
                raw_text="LED전광판 1식",
            )
        ],
        region="충북 음성",
        install_schedule_text="2026년 3월",
        required_keywords=["LED전광판", "디스플레이"],
        metadata={
            "source": "frontend_project_payload",
            "api_key": "must_not_be_persisted",
            "endpoint": "must_not_be_persisted",
        },
    )
    return RequirementIngestionResult(
        request_id="request_test",
        source_type="frontend_project_payload",
        source_path=None,
        requirement=requirement,
        embedding_text="고객사: 일강이앤아이\n카테고리: LED전광판",
        embedding_vector=[0.1, 0.2, 0.3],
        embedding_dim=3,
        raw_text_preview="회의실 디스플레이 설치",
        parser_warnings=[],
        parser_raw_matches={},
        ingestion_warnings=[],
        metadata={"requirement_source": "frontend_project_payload"},
    )


def _build_quote_ingestion_result(request_id: str) -> QuoteIngestionResult:
    quote = QuoteDocument(
        vendor_name="효성ITX",
        quote_id="quote_001",
        received_at=datetime(2026, 6, 13, 10, 0, 0),
        project_name="회의실 디스플레이",
        total_supply_price=4_000_000,
        total_with_vat=4_400_000,
        line_items=[
            LineItem(
                name="LED Display",
                category=LineItemCategory.DISPLAY,
                quantity=20,
                unit="EA",
                unit_price=200_000,
                total_price=4_000_000,
            )
        ],
    )
    return QuoteIngestionResult(
        quote_id="quote_001",
        request_id=request_id,
        source_file_path="data/sample.pdf",
        quote=quote,
        embedding_text="quote embedding text",
        embedding_vector=[0.4, 0.5, 0.6],
        embedding_dim=3,
        ocr_text_preview="safe preview",
        parser_warnings=[],
        parser_raw_matches={"ocr_full_text": "must_not_be_persisted"},
        ingestion_warnings=[],
        metadata={},
    )


def _build_recommendation_result(request_id: str) -> RecommendationPipelineResult:
    item = RecommendationItem(
        rank=1,
        quote_id="quote_001",
        partner_name="효성ITX",
        partner_found=True,
        is_premium=True,
        success_rate=0.2,
        response_speed="normal",
        financial_status="normal",
        business_rule_passed=True,
        business_stage="passed",
        filter_reasons=[],
        business_sort_key=[1, 2, 3],
        vendor_name="효성ITX",
        project_name="회의실 디스플레이",
        source_file_path="data/sample.pdf",
        final_score=90.0,
        spec_score=90.0,
        price_score=80.0,
        delivery_score=70.0,
        warranty_score=80.0,
        installation_score=85.0,
        cosine_similarity=0.9,
        total_supply_price=4_000_000,
        total_with_vat=4_400_000,
        delivery_weeks=4,
        delivery_basis_raw="발주 후 4주",
        warranty_months=12,
        line_item_count=1,
        check_required=[],
        score_breakdown={"price": 80.0},
    )
    return RecommendationPipelineResult(
        request_id=request_id,
        customer_name="일강이앤아이",
        top_n=3,
        items=[item],
        all_items=[item],
        failed_candidates=[],
        filtered_candidates=[],
        metadata={},
    )


def _build_partner_matching_result(request_id: str) -> PartnerMatchingResult:
    candidate = PartnerMatchCandidate(
        partner_name="효성ITX",
        specialty_tags=["LED전광판"],
        semantic_similarity_score=90.0,
        cosine_similarity=0.9,
        is_premium=True,
        success_rate=0.2,
        response_speed="normal",
        financial_status="normal",
        is_excluded=False,
        business_rule_passed=True,
        business_stage="selected_top_n",
        filter_reasons=[],
        check_required=[],
        sort_key=[90.0],
        rank=1,
        company_location="서울",
        installation_count=12,
        final_score=90.0,
        score_breakdown={"semantic_score": 90.0},
    )
    return PartnerMatchingResult(
        request_id=request_id,
        customer_name="일강이앤아이",
        top_n=10,
        candidates=[candidate],
        all_candidates=[candidate],
        filtered_candidates=[],
        metadata={"partner_count": 1},
    )


if __name__ == "__main__":
    main()
