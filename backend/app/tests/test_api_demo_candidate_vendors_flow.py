import json
from pathlib import Path

from config.paths import DATA_DIR, OUTPUT_DIR
from services.api_demo.app import coerce_candidate_vendors_payload
from services.api_demo.routers import (
    compare_quotes,
    create_project,
    get_candidate_vendors,
    run_match,
    run_candidate_vendors,
    upload_quote_paths,
)
from services.api_demo.schemas import (
    CandidateVendorRequest,
    CandidateVendorsRequest,
    CompareRequest,
    MatchRunRequest,
    ProjectCreateRequest,
)


OUTPUT_PATH = OUTPUT_DIR / "api_demo_candidate_vendors_response.json"
SENSITIVE_KEYS = {
    "embedding_vector",
    "requirement_embedding",
    "partner_embedding",
    "ocr_text",
    "ocr_full_text",
    "api_key",
    "endpoint",
    "deployment",
}


def remove_sensitive_fields(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                continue
            cleaned[key] = remove_sensitive_fields(item)
        return cleaned
    if isinstance(value, list):
        return [remove_sensitive_fields(item) for item in value]
    return value


def write_candidate_vendors_output(response: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    safe_response = remove_sensitive_fields(response)
    OUTPUT_PATH.write_text(
        json.dumps(safe_response, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        "Candidate vendors response saved to "
        "data/demo_outputs/api_demo_candidate_vendors_response.json"
    )
    print("Top candidate vendors:")
    for candidate in safe_response.get("data", {}).get("candidate_vendors", [])[:3]:
        print(
            f"{candidate.get('rank')}. {candidate.get('vendor_name')} - "
            f"final_score {candidate.get('final_score')} "
            f"(semantic {candidate.get('semantic_similarity_score')})"
        )


def assert_candidate_vendors_output_file() -> None:
    assert OUTPUT_PATH.exists()
    saved = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    assert saved["ok"] is True
    assert "data" in saved
    assert len(saved["data"]["candidate_vendors"]) > 0
    assert len(saved["data"]["selected_vendor_names"]) > 0
    assert "metadata" in saved["data"]
    assert_candidate_vendors_full_list_contract(saved)

    text = OUTPUT_PATH.read_text(encoding="utf-8")
    assert "embedding_vector" not in text
    assert "requirement_embedding" not in text
    assert "partner_embedding" not in text
    assert "api_key" not in text.lower()
    assert "ocr_text" not in text
    assert "C:\\" not in text
    assert "/Users/" not in text


def assert_candidate_vendors_full_list_contract(response: dict) -> None:
    data = response["data"]
    candidate_vendors = data["candidate_vendors"]
    metadata = data["metadata"]
    selected = [vendor for vendor in candidate_vendors if vendor["business_rule_passed"]]
    not_selected = [
        vendor for vendor in candidate_vendors if not vendor["business_rule_passed"]
    ]
    ranks = [vendor["rank"] for vendor in candidate_vendors]

    assert len(candidate_vendors) == metadata["partner_count"]
    assert metadata["partner_count"] >= 50
    assert len(selected) == data["top_n"]
    assert len(not_selected) == metadata["partner_count"] - data["top_n"]
    assert data["selected_vendor_names"] == [vendor["vendor_name"] for vendor in selected]
    assert "requested_vendor_ids" in data
    assert isinstance(data["requested_vendor_ids"], list)
    assert ranks == sorted(ranks)
    assert ranks[0] == 1
    assert metadata["candidate_count"] == metadata["partner_count"]
    assert metadata["selected_count"] == len(selected)
    assert metadata["not_selected_count"] == len(not_selected)
    scores = [vendor["final_score"] for vendor in candidate_vendors]
    assert max(scores) - min(scores) >= 10
    for vendor in candidate_vendors:
        assert "installation_count" in vendor
        assert "final_score" in vendor
        assert "score_breakdown" in vendor
        assert "specialty_match_score" in vendor["score_breakdown"]
        assert "semantic_score" in vendor["score_breakdown"]
        assert "semantic_score_calibrated" in vendor
        assert "special_notes" in vendor
        assert isinstance(vendor["special_notes"], list)

    top10 = candidate_vendors[:10]
    assert any("LED전광판" in vendor["specialty_tags"] for vendor in top10)
    assert top10[0]["score_breakdown"]["specialty_match_score"] >= 80
    assert (
        "LED전광판" in top10[0]["specialty_tags"]
        or "비디오월" in top10[0]["specialty_tags"]
    )


def _demo_request_text() -> str:
    return "\n".join(
        [
            "프로젝트명: 충북 음성 회의실 디스플레이",
            "활용 용도: 회의실 태양광 발전 현황 확인",
            "디스플레이 크기: 3000x2000mm",
            "수량: 1식",
            "운영 시간: 업무시간 운영",
            "카테고리: LED전광판",
            "예산 상한: 3000만원",
            "현재 단계: 실시설계 단계",
            "우선 검토 기준: 가격 우선",
            "추가 요청사항: 실내 설치 필요",
            "첨부 메모: 없음",
        ]
    )


def _demo_file_paths(limit: int = 1) -> list[Path]:
    if not DATA_DIR.exists():
        return []
    files = [
        path
        for path in sorted(DATA_DIR.iterdir())
        if path.suffix.lower() in {".pdf", ".xlsx", ".png", ".jpg", ".jpeg"}
    ]
    video_wall_files = [path for path in files if "비디오월" in path.stem]
    if len(video_wall_files) >= limit:
        return video_wall_files[:limit]
    return files[:limit]


def _create_project():
    return create_project(
        ProjectCreateRequest(
            company_name="일강이앤아이",
            location="충북 음성",
            deadline="2026년 3월",
            request_text=_demo_request_text(),
        )
    )


def test_candidate_vendors_post_and_get() -> None:
    project = _create_project()
    response = run_candidate_vendors(
        project["project_id"],
        CandidateVendorsRequest(top_n=5, similarity_threshold=0.0),
    )
    assert response["ok"] is True
    data = response["data"]
    assert data["candidate_vendors"]
    assert data["selected_vendor_names"]
    assert_candidate_vendors_full_list_contract(response)
    assert "embedding_vector" not in json.dumps(response, ensure_ascii=False)

    get_response = get_candidate_vendors(project["project_id"])
    assert get_response["ok"] is True
    assert get_response["data"]["selected_vendor_names"] == data["selected_vendor_names"]


def test_candidate_vendors_legacy_quote_top_n_body_conversion() -> None:
    project = _create_project()
    legacy_body = CandidateVendorRequest(quote_top_n=5)
    payload = coerce_candidate_vendors_payload(legacy_body)
    assert payload is not None
    assert payload.top_n == 5
    payload.similarity_threshold = 0.0

    response = run_candidate_vendors(project["project_id"], payload)
    assert response["ok"] is True
    assert response["data"]["top_n"] == 5
    assert response["data"]["candidate_vendors"]
    assert_candidate_vendors_full_list_contract(response)
    assert "embedding_vector" not in json.dumps(response, ensure_ascii=False)


def test_candidate_vendors_route_dict_quote_top_n_conversion() -> None:
    payload = coerce_candidate_vendors_payload({"quote_top_n": 5})
    assert payload is not None
    assert isinstance(payload, CandidateVendorsRequest)
    assert payload.top_n == 5
    assert payload.similarity_threshold == 60.0


def test_candidate_vendors_rejects_int_payload() -> None:
    project = _create_project()
    try:
        run_candidate_vendors(project["project_id"], 5)
    except TypeError as exc:
        assert "CandidateVendorsRequest or None" in str(exc)
        assert "int" in str(exc)
    else:
        raise AssertionError("run_candidate_vendors should reject int payload")


def test_candidate_vendors_none_payload_uses_defaults() -> None:
    project = _create_project()
    response = run_candidate_vendors(project["project_id"], None)
    assert response["ok"] is True
    assert response["data"]["top_n"] == 10
    assert response["data"]["similarity_threshold"] == 60.0
    assert response["data"]["candidate_vendors"]
    assert_candidate_vendors_full_list_contract(response)
    assert "embedding_vector" not in json.dumps(response, ensure_ascii=False)
    write_candidate_vendors_output(response)
    assert_candidate_vendors_output_file()


def test_candidate_vendors_body_override() -> None:
    project = _create_project()
    response = run_candidate_vendors(
        project["project_id"],
        CandidateVendorsRequest(
            request_text="서울 회의실 비디오월 2x2 설치 검토, 납기 2개월 이내",
            top_n=3,
            similarity_threshold=0.0,
        ),
    )
    assert response["ok"] is True
    assert response["data"]["top_n"] == 3
    assert response["data"]["candidate_vendors"]
    assert "embedding_vector" not in json.dumps(response, ensure_ascii=False)


def test_get_candidate_vendors_not_found() -> None:
    project = _create_project()
    response = get_candidate_vendors(project["project_id"])
    assert response["ok"] is False
    assert response["error"] == "candidate vendors result not found"


def test_quote_upload_candidate_vendor_link() -> None:
    file_paths = _demo_file_paths(limit=4)
    if not file_paths:
        print("demo quote files not found; skipping quote upload link check")
        return

    project = _create_project()
    run_candidate_vendors(
        project["project_id"],
        CandidateVendorsRequest(top_n=10, similarity_threshold=0.0),
    )
    quote_response = upload_quote_paths(project["project_id"], file_paths)
    assert quote_response["processed_count"] > 0
    selected_count = 0
    non_selected_count = 0
    for quote in quote_response["quotes"]:
        link = quote.get("candidate_vendor_link")
        assert link is not None
        assert link["candidate_vendor_matching_executed"] is True
        assert isinstance(link["is_selected_vendor"], bool)
        selected_count += 1 if link["is_selected_vendor"] else 0
        non_selected_count += 0 if link["is_selected_vendor"] else 1
        assert "embedding_vector" not in json.dumps(quote, ensure_ascii=False)
    assert selected_count > 0
    assert non_selected_count > 0

    match_response = run_match(
        project["project_id"],
        MatchRunRequest(quote_top_n=3, run_explanation=False),
    )
    recommendation = match_response["recommendation"]
    product_group_filter = recommendation["metadata"]["product_group_filter"]
    assert product_group_filter["source"] == "grouped_product_group"
    assert product_group_filter["enabled"] is False
    assert len(recommendation["all_items"]) == quote_response["processed_count"]
    assert product_group_filter["input_quote_count"] == quote_response["processed_count"]
    assert match_response["recommendation_groups"]
    assert match_response["metadata"]["candidate_vendor_filter_applied"] is False
    assert all(item["business_rule_passed"] is True for item in recommendation["all_items"])
    serialized = json.dumps(recommendation, ensure_ascii=False)
    assert "후보 업체에 포함되지 않음" not in serialized
    assert "파트너 매칭 단계 미선정 업체" not in serialized
    assert "추천 리스트에 없던 업체" not in serialized

    compare_response = compare_quotes(project["project_id"], CompareRequest())
    assert len(compare_response["rows"]) == quote_response["processed_count"]
    assert compare_response["metadata"]["grouped_by_product_group"] is True
    assert compare_response["groups"]
    for row in compare_response["rows"]:
        assert row.get("product_group")
        assert row.get("install_location") == project["region"]
        assert row.get("conditions", {}).get("install_location") == project["region"]
        assert row.get("company_location") != row.get("install_location")
    assert non_selected_count > 0
    assert "후보 업체에 포함되지 않음" not in json.dumps(
        compare_response,
        ensure_ascii=False,
    )


def test_quote_flow_without_candidate_vendors_keeps_compatibility() -> None:
    file_paths = _demo_file_paths()
    if not file_paths:
        print("demo quote files not found; skipping no-candidate compatibility check")
        return

    project = _create_project()
    quote_response = upload_quote_paths(project["project_id"], file_paths)
    assert quote_response["processed_count"] > 0
    assert all("candidate_vendor_link" not in quote for quote in quote_response["quotes"])

    match_response = run_match(
        project["project_id"],
        MatchRunRequest(quote_top_n=1, run_explanation=False),
    )
    assert match_response["recommendation"]["items"]
    assert match_response["metadata"]["candidate_vendor_matching_executed"] is False
    assert match_response["metadata"]["selected_vendor_names"] == []


def main() -> None:
    test_candidate_vendors_post_and_get()
    test_candidate_vendors_legacy_quote_top_n_body_conversion()
    test_candidate_vendors_route_dict_quote_top_n_conversion()
    test_candidate_vendors_rejects_int_payload()
    test_candidate_vendors_none_payload_uses_defaults()
    test_candidate_vendors_body_override()
    test_get_candidate_vendors_not_found()
    test_quote_upload_candidate_vendor_link()
    test_quote_flow_without_candidate_vendors_keeps_compatibility()
    print("api demo candidate vendors flow tests passed")


if __name__ == "__main__":
    main()
