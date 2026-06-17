from __future__ import annotations

from api.v1.routes import CandidateVendorUpdateRequest
from services.api_demo.response_builders import build_candidate_vendors_response
from services.api_demo.store import ApiDemoStore
from services.partner_matching.schemas import (
    PartnerMatchCandidate,
    PartnerMatchingResult,
)
from services.requirement.schemas import RequirementInfo
from services.requirement_ingestion.schemas import RequirementIngestionResult


def test_update_candidate_vendor_fields_in_memory() -> None:
    store = ApiDemoStore(persistence=None)
    record = _save_candidate_vendors(store)
    candidate = record.candidate_vendor_result.all_candidates[0]

    updated = store.update_candidate_vendor_fields(
        "project_test",
        "테스트공급사",
        {
            "response_speed": "fast",
            "financial_status": "good",
            "company_location": "서울특별시 강남구",
            "installation_count": 25,
        },
    )

    assert updated is True
    assert candidate.response_speed == "fast"
    assert candidate.financial_status == "good"
    assert candidate.company_location == "서울특별시 강남구"
    assert candidate.installation_count == 25
    assert candidate.metadata["manual_update"]["response_speed"] == "fast"


def test_unknown_vendor_returns_false() -> None:
    store = ApiDemoStore(persistence=None)
    _save_candidate_vendors(store)

    updated = store.update_candidate_vendor_fields(
        "project_test",
        "없는공급사",
        {"response_speed": "fast"},
    )

    assert updated is False


def test_unsupported_fields_are_ignored() -> None:
    store = ApiDemoStore(persistence=None)
    record = _save_candidate_vendors(store)
    candidate = record.candidate_vendor_result.all_candidates[0]

    updated = store.update_candidate_vendor_fields(
        "project_test",
        "테스트공급사",
        {
            "response_speed": "fast",
            "final_score": 0,
            "business_rule_passed": False,
        },
    )

    assert updated is True
    assert candidate.response_speed == "fast"
    assert candidate.final_score == 90.0
    assert candidate.business_rule_passed is True


def test_special_notes_string_updates_metadata_and_response() -> None:
    payload = CandidateVendorUpdateRequest(special_notes="전기공사 별도 확인 필요")
    update_fields = payload.model_dump(exclude_none=True)
    store = ApiDemoStore(persistence=None)
    record = _save_candidate_vendors(store)
    candidate = record.candidate_vendor_result.all_candidates[0]

    updated = store.update_candidate_vendor_fields(
        "project_test",
        candidate.partner_name,
        {
            **update_fields,
            "final_score": 0,
        },
    )
    response = build_candidate_vendors_response("project_test", record)

    assert updated is True
    assert candidate.metadata["special_notes"] == ["전기공사 별도 확인 필요"]
    assert candidate.metadata["manual_update"]["special_notes"] == ["전기공사 별도 확인 필요"]
    assert candidate.final_score == 90.0
    assert response["data"]["candidate_vendors"][0]["special_notes"] == [
        "전기공사 별도 확인 필요"
    ]


def test_special_notes_list_updates_metadata() -> None:
    payload = CandidateVendorUpdateRequest(
        special_notes=["전기공사 별도", "현장 실사 후 비용 변경 가능"]
    )
    store = ApiDemoStore(persistence=None)
    record = _save_candidate_vendors(store)
    candidate = record.candidate_vendor_result.all_candidates[0]

    updated = store.update_candidate_vendor_fields(
        "project_test",
        candidate.partner_name,
        payload.model_dump(exclude_none=True),
    )

    assert updated is True
    assert candidate.metadata["special_notes"] == [
        "전기공사 별도",
        "현장 실사 후 비용 변경 가능",
    ]


def test_get_candidate_vendors_returns_updated_cached_record() -> None:
    store = ApiDemoStore(persistence=None)
    _save_candidate_vendors(store)

    updated = store.update_candidate_vendor_fields(
        "project_test",
        "테스트공급사",
        {"company_location": "서울특별시 강남구"},
    )
    cached = store.get_candidate_vendors("project_test")

    assert updated is True
    assert cached is not None
    assert (
        cached.candidate_vendor_result.all_candidates[0].company_location
        == "서울특별시 강남구"
    )


def test_all_candidate_lists_are_synchronized() -> None:
    store = ApiDemoStore(persistence=None)
    all_candidate = _candidate("테스트공급사")
    selected_copy = _candidate("테스트공급사")
    filtered_copy = _candidate("테스트공급사")
    result = PartnerMatchingResult(
        request_id="request_test",
        customer_name="테스트고객",
        top_n=10,
        candidates=[selected_copy],
        all_candidates=[all_candidate],
        filtered_candidates=[filtered_copy],
        metadata={},
    )
    store.save_candidate_vendors(
        project_id="project_test",
        requirement_result=_requirement_result(),
        candidate_vendor_result=result,
        top_n=10,
        similarity_threshold=60.0,
    )

    updated = store.update_candidate_vendor_fields(
        "project_test",
        "테스트공급사",
        {"installation_count": 25},
    )

    assert updated is True
    assert all_candidate.installation_count == 25
    assert selected_copy.installation_count == 25
    assert filtered_copy.installation_count == 25


def test_vendor_name_metadata_fallback_matches() -> None:
    store = ApiDemoStore(persistence=None)
    candidate = _candidate("표시명")
    candidate.metadata["vendor_name"] = "메타공급사"
    result = PartnerMatchingResult(
        request_id="request_test",
        customer_name="테스트고객",
        top_n=10,
        candidates=[],
        all_candidates=[candidate],
        filtered_candidates=[],
        metadata={},
    )
    store.save_candidate_vendors(
        project_id="project_test",
        requirement_result=_requirement_result(),
        candidate_vendor_result=result,
        top_n=10,
        similarity_threshold=60.0,
    )

    updated = store.update_candidate_vendor_fields(
        "project_test",
        "메타 공급사",
        {"financial_status": "good"},
    )

    assert updated is True
    assert candidate.financial_status == "good"


def _save_candidate_vendors(store: ApiDemoStore):
    result = PartnerMatchingResult(
        request_id="request_test",
        customer_name="테스트고객",
        top_n=10,
        candidates=[],
        all_candidates=[_candidate("테스트공급사")],
        filtered_candidates=[],
        metadata={},
    )
    return store.save_candidate_vendors(
        project_id="project_test",
        requirement_result=_requirement_result(),
        candidate_vendor_result=result,
        top_n=10,
        similarity_threshold=60.0,
    )


def _candidate(name: str) -> PartnerMatchCandidate:
    return PartnerMatchCandidate(
        partner_name=name,
        specialty_tags=["LED전광판"],
        semantic_similarity_score=90.0,
        cosine_similarity=0.9,
        is_premium=False,
        success_rate=0.1,
        response_speed="normal",
        financial_status="normal",
        is_excluded=False,
        business_rule_passed=True,
        business_stage="selected_top_n",
        filter_reasons=[],
        check_required=[],
        sort_key=[],
        rank=1,
        company_location="서울",
        installation_count=3,
        final_score=90.0,
        metadata={"partner_name": name},
    )


def _requirement_result() -> RequirementIngestionResult:
    requirement = RequirementInfo(
        raw_text="LED전광판 설치",
        customer_name="테스트고객",
        request_summary="LED전광판 설치",
        required_keywords=["LED전광판"],
    )
    return RequirementIngestionResult(
        request_id="request_test",
        source_type="structured",
        source_path=None,
        requirement=requirement,
        embedding_text="LED전광판 설치",
        embedding_vector=[0.1, 0.2, 0.3],
        embedding_dim=3,
        raw_text_preview="LED전광판 설치",
        parser_warnings=[],
        ingestion_warnings=[],
        metadata={"requirement_source": "test"},
    )


def main() -> None:
    test_update_candidate_vendor_fields_in_memory()
    test_unknown_vendor_returns_false()
    test_unsupported_fields_are_ignored()
    test_special_notes_string_updates_metadata_and_response()
    test_special_notes_list_updates_metadata()
    test_get_candidate_vendors_returns_updated_cached_record()
    test_all_candidate_lists_are_synchronized()
    test_vendor_name_metadata_fallback_matches()
    print("candidate vendor cache sync tests passed")


if __name__ == "__main__":
    main()
