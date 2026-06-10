import json
import os
from pathlib import Path

from config.paths import DATA_DIR, OUTPUT_DIR
from services.api_demo.enums import CellStatus
from services.api_demo.response_builders import strip_heavy_fields
from services.api_demo.routers import (
    compare_quotes,
    create_project,
    get_candidate_vendors,
    get_explanation,
    get_matches,
    run_candidate_vendors,
    run_match,
    upload_quote_paths,
)
from services.api_demo.schemas import (
    CandidateVendorsRequest,
    CompareRequest,
    MatchRunRequest,
    ProjectCreateRequest,
)
from services.api_demo.store import store


ALLOWED_STATUSES = {status.value for status in CellStatus}


def get_demo_request_text() -> str:
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


def find_demo_files() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    files = [
        path
        for path in sorted(DATA_DIR.iterdir())
        if path.suffix.lower() in {".pdf", ".xlsx", ".png", ".jpg", ".jpeg"}
    ]
    video_wall_files = [path for path in files if "비디오월" in path.stem]
    if len(video_wall_files) >= 3:
        return video_wall_files[:3]
    return files[:3]


def main() -> None:
    full_result = {}

    print("========== 1. Project 생성 ==========")
    project_response = create_project(
        ProjectCreateRequest(
            company_name="일강이앤아이",
            location="충북 음성",
            deadline="2026년 3월",
            request_text=get_demo_request_text(),
        )
    )
    project_id = project_response["project_id"]
    print("project_id:", project_id)
    print("customer_name:", project_response["customer_name"])
    print("products:", project_response["products"])
    assert project_response["customer_name"] == "일강이앤아이"
    assert project_response["region"] == "충북 음성"
    assert project_response["install_schedule_text"] == "2026년 3월"
    assert project_response["products"]
    for removed_field in [
        "project_name",
        "project_stage",
        "budget_max",
        "requirement_source",
    ]:
        assert removed_field not in project_response
    assert "embedding_vector" not in json.dumps(project_response, ensure_ascii=False)

    project_record = store.get_project(project_id)
    assert project_record is not None
    requirement = project_record.requirement_result.requirement
    assert requirement.project_name == "충북 음성 회의실 디스플레이"
    assert requirement.project_stage == "실시설계 단계"
    assert requirement.budget_max == 30000000
    assert project_record.requirement_result.metadata["requirement_source"] == "frontend_project_payload"
    assert requirement.metadata["source"] == "frontend_project_payload"
    full_result["project_create"] = project_response

    print("\n========== 2. Candidate Vendors 실행 ==========")
    candidate_response = run_candidate_vendors(
        project_id,
        CandidateVendorsRequest(top_n=10, similarity_threshold=0.0),
    )
    candidate_data = candidate_response["data"]
    print("candidate_count:", len(candidate_data["candidate_vendors"]))
    print("selected_vendor_names:", candidate_data["selected_vendor_names"])
    assert candidate_response["ok"] is True
    assert candidate_data["candidate_vendors"]
    assert candidate_data["selected_vendor_names"]
    assert "embedding_vector" not in json.dumps(candidate_response, ensure_ascii=False)
    assert get_candidate_vendors(project_id)["ok"] is True
    full_result["candidate_vendors"] = candidate_response

    print("\n========== 3. Quote Pool 생성 ==========")
    file_paths = find_demo_files()
    if not file_paths:
        print("테스트할 견적서 파일이 없습니다.")
        return
    quote_response = upload_quote_paths(project_id, file_paths)
    print("processed_count:", quote_response["processed_count"])
    assert quote_response["processed_count"] > 0
    selected_vendor_quote_count = sum(
        1
        for quote in quote_response["quotes"]
        if quote.get("candidate_vendor_link", {}).get("is_selected_vendor")
    )
    non_selected_vendor_quote_count = quote_response["processed_count"] - selected_vendor_quote_count
    print("selected vendor quote count:", selected_vendor_quote_count)
    print("non-selected vendor quote count:", non_selected_vendor_quote_count)
    assert selected_vendor_quote_count > 0
    assert non_selected_vendor_quote_count > 0
    assert "embedding_vector" not in json.dumps(quote_response, ensure_ascii=False)
    full_result["quote_upload"] = quote_response

    print("\n========== 4. Match 실행 ==========")
    match_response = run_match(
        project_id,
        MatchRunRequest(quote_top_n=3, run_explanation=False),
    )
    match_id = match_response["match_id"]
    recommendation = match_response["recommendation"]
    print("recommendation count:", len(recommendation["items"]))
    assert recommendation["items"]
    assert len(recommendation["all_items"]) == quote_response["processed_count"]
    assert match_response["metadata"]["candidate_vendor_filter_applied"] is False
    assert recommendation["metadata"]["candidate_vendor_filter_applied"] is False
    assert all(item["business_rule_passed"] is True for item in recommendation["all_items"])
    full_result["match_run"] = match_response

    print("\n========== 5. Dashboard 조회 ==========")
    dashboard_response = get_matches(project_id)
    assert dashboard_response["recommendation"]["items"]
    full_result["dashboard"] = dashboard_response

    print("\n========== 6. Explanation 조회 ==========")
    explanation_response = get_explanation(project_id, match_id)
    print("overall_summary:", explanation_response["overall_summary"])
    assert explanation_response["overall_summary"]
    selected_provider = os.getenv("EXPLANATION_PROVIDER")
    if selected_provider == "azure_openai":
        assert explanation_response["provider"] == "azure_openai"
    explanation_text = json.dumps(explanation_response, ensure_ascii=False)
    assert "후보 업체에 포함되지 않음" not in explanation_text
    assert "파트너 매칭 단계 미선정 업체" not in explanation_text
    assert "추천 리스트에 없던 업체" not in explanation_text
    full_result["explanation"] = explanation_response

    print("\n========== 7. Compare 생성 ==========")
    compare_response = compare_quotes(project_id, CompareRequest())
    print("rows:", len(compare_response["rows"]))
    assert len(compare_response["rows"]) == quote_response["processed_count"]
    expected_install_location = project_response["region"]
    for row in compare_response["rows"]:
        assert "candidate_vendor_link" in row
        assert "comparison_risks" in row
        assert row.get("install_location") == expected_install_location
        assert row.get("conditions", {}).get("install_location") == expected_install_location
        assert row.get("company_location") != row.get("install_location")
        assert not any("가격 차이 5% 초과" in item for item in row["check_required"])
    validate_compare_statuses(compare_response)
    full_result["compare"] = compare_response

    compare_output_path = OUTPUT_DIR / "api_demo_compare_response.json"
    compare_output_path.parent.mkdir(parents=True, exist_ok=True)
    compare_output_path.write_text(
        json.dumps(strip_heavy_fields(compare_response), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Compare response JSON saved:", compare_output_path)

    output_path = OUTPUT_DIR / "api_demo_flow_result.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(strip_heavy_fields(full_result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Full API response JSON saved:", output_path)


def collect_status_values(obj) -> list[str]:
    values = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "status":
                values.append(value)
            else:
                values.extend(collect_status_values(value))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(collect_status_values(item))
    return values


def validate_compare_statuses(compare_response) -> None:
    statuses = collect_status_values(compare_response)
    assert statuses
    assert all(status in ALLOWED_STATUSES for status in statuses)

    for row in compare_response["rows"]:
        highlights = row.get("highlights") or {}
        assert set(highlights) == {
            "is_lowest_total_price",
            "is_fastest_delivery",
            "is_longest_warranty",
            "is_highest_score",
        }
        assert all(isinstance(value, bool) for value in highlights.values())


if __name__ == "__main__":
    main()
