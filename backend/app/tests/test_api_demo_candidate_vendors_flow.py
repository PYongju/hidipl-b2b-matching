import json
from pathlib import Path

from config.paths import DATA_DIR
from services.api_demo.routers import (
    compare_quotes,
    create_project,
    get_candidate_vendors,
    run_match,
    run_candidate_vendors,
    upload_quote_paths,
)
from services.api_demo.schemas import (
    CandidateVendorsRequest,
    CompareRequest,
    MatchRunRequest,
    ProjectCreateRequest,
)


def _demo_request_text() -> str:
    return """
고객명: 일강이앤아이
지역: 충북 음성
요청사항: 회의실 태양광 발전 현황 확인용 LED 전광판 또는 비디오월 설치 검토
제품 1: LED P1.56 3000 x 2000mm
제품 2: 46인치 비디오월 3x3
일정: 3개월 내외
"""


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
            deadline="3개월 내외",
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
    assert "embedding_vector" not in json.dumps(response, ensure_ascii=False)

    get_response = get_candidate_vendors(project["project_id"])
    assert get_response["ok"] is True
    assert get_response["data"]["selected_vendor_names"] == data["selected_vendor_names"]


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
    assert len(recommendation["all_items"]) == quote_response["processed_count"]
    assert match_response["metadata"]["candidate_vendor_filter_applied"] is False
    assert all(item["business_rule_passed"] is True for item in recommendation["all_items"])
    serialized = json.dumps(recommendation, ensure_ascii=False)
    assert "후보 업체에 포함되지 않음" not in serialized
    assert "파트너 매칭 단계 미선정 업체" not in serialized
    assert "추천 리스트에 없던 업체" not in serialized

    compare_response = compare_quotes(project["project_id"], CompareRequest())
    assert len(compare_response["rows"]) == quote_response["processed_count"]
    for row in compare_response["rows"]:
        assert row.get("install_location") == project["region"]
        assert row.get("conditions", {}).get("install_location") == project["region"]
        assert row.get("company_location") != row.get("install_location")
    assert any(
        row.get("candidate_vendor_link", {}).get("is_selected_vendor") is False
        for row in compare_response["rows"]
    )
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
    test_candidate_vendors_body_override()
    test_get_candidate_vendors_not_found()
    test_quote_upload_candidate_vendor_link()
    test_quote_flow_without_candidate_vendors_keeps_compatibility()
    print("api demo candidate vendors flow tests passed")


if __name__ == "__main__":
    main()
