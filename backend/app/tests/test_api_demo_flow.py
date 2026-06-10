import json
import os
from pathlib import Path
from pprint import pprint

from config.paths import DATA_DIR, OUTPUT_DIR
from services.api_demo.enums import CellStatus
from services.api_demo.response_builders import _resolve_install_location, strip_heavy_fields
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
KOREAN_STATUS_VALUES = {
    "포함",
    "미기재",
    "별도 청구",
    "확인 필요",
    "파싱 실패",
}


def get_demo_request_text() -> str:
    return """안녕하세요. 신규 고객 건 연결드립니다.

1. 고객사: 일강이앤아이
2. 견적 요청 내용: 회의실 내 태양광 발전 현황 확인을 위한 비디오월 또는 LED 전광판 검토
(1) 46인치 비디오월 3x3
(2) LED P1.56 3,000 x 2,000mm
3. 일정: 3개월 내외
4. 지역: 충북 음성
5. 단계: 견적 확인 후 내부 보고 예정
"""


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
            deadline="3개월 내외",
            request_text=get_demo_request_text(),
        )
    )
    project_id = project_response["project_id"]
    print("POST /api/v1/projects")
    print("project_id:", project_id)
    print("customer_name:", project_response["customer_name"])
    print("products:")
    pprint(project_response["products"])
    assert project_response["embedding_dim"] is None or project_response["embedding_dim"] > 0
    full_result["project_create"] = project_response

    print("\n========== 2. Candidate Vendors 실행 ==========")
    candidate_response = run_candidate_vendors(
        project_id,
        CandidateVendorsRequest(top_n=10, similarity_threshold=0.0),
    )
    print("POST /api/v1/projects/{id}/candidate-vendors")
    candidate_data = candidate_response["data"]
    print("candidate_count:", len(candidate_data["candidate_vendors"]))
    print("selected_vendor_names:", candidate_data["selected_vendor_names"])
    for candidate in candidate_data["candidate_vendors"][:3]:
        print(
            candidate["rank"],
            candidate["vendor_name"],
            candidate["semantic_similarity_score"],
            "location:",
            candidate["company_location"],
        )
    assert candidate_response["ok"] is True
    assert candidate_data["candidate_vendors"]
    assert candidate_data["selected_vendor_names"]
    assert "embedding_vector" not in json.dumps(candidate_response, ensure_ascii=False)
    get_candidate_response = get_candidate_vendors(project_id)
    assert get_candidate_response["ok"] is True
    assert (
        get_candidate_response["data"]["selected_vendor_names"]
        == candidate_data["selected_vendor_names"]
    )
    full_result["candidate_vendors"] = candidate_response

    print("\n========== 3. Quote Pool 생성 ==========")
    file_paths = find_demo_files()
    if not file_paths:
        print("테스트할 견적서 파일이 없습니다.")
        return
    quote_response = upload_quote_paths(project_id, file_paths)
    print("POST /api/v1/projects/{id}/quotes")
    print("processed_count:", quote_response["processed_count"])
    print("quote_pool_count:", len(quote_response["quotes"]))
    print("quotes:")
    for quote in quote_response["quotes"]:
        print(
            quote["quote_id"],
            quote["vendor_name"],
            "vendor_snapshot:",
            bool(quote["vendor_snapshot"]),
            "candidate_vendor_link:",
            quote.get("candidate_vendor_link"),
        )
        assert quote.get("candidate_vendor_link", {}).get(
            "candidate_vendor_matching_executed"
        ) is True
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
    full_result["quote_upload"] = quote_response

    print("\n========== 4. Match 실행 ==========")
    match_response = run_match(
        project_id,
        MatchRunRequest(quote_top_n=3, run_explanation=False),
    )
    match_id = match_response["match_id"]
    print("POST /api/v1/projects/{id}/matches")
    print("match_id:", match_id)
    print("QuoteRanking Top 3:")
    for item in match_response["recommendation"]["items"]:
        print(
            item["rank"],
            item["vendor_name"],
            item["final_score"],
            "matched_rules:",
            item["matched_rules"],
            "vendor_snapshot:",
            item["vendor_snapshot"],
        )
    assert match_response["recommendation"]["items"]
    assert (
        len(match_response["recommendation"]["all_items"])
        == quote_response["processed_count"]
    )
    assert match_response["metadata"]["candidate_vendor_matching_executed"] is True
    assert match_response["metadata"]["selected_vendor_names"]
    assert match_response["metadata"]["candidate_vendor_filter_applied"] is False
    assert match_response["recommendation"]["metadata"]["candidate_vendor_filter_applied"] is False
    all_ranked_vendor_names = {
        item["vendor_name"] for item in match_response["recommendation"]["all_items"]
    }
    uploaded_vendor_names = {quote["vendor_name"] for quote in quote_response["quotes"]}
    assert uploaded_vendor_names <= all_ranked_vendor_names
    forbidden_candidate_text = " ".join(
        json.dumps(item, ensure_ascii=False)
        for item in match_response["recommendation"]["all_items"]
    )
    assert "후보 업체에 포함되지 않음" not in forbidden_candidate_text
    assert "파트너 매칭 단계 미선정 업체" not in forbidden_candidate_text
    assert "추천 리스트에 없던 업체" not in forbidden_candidate_text
    full_result["match_run"] = match_response

    print("\n========== 5. Dashboard 조회 ==========")
    dashboard_response = get_matches(project_id)
    print("GET /api/v1/projects/{id}/matches")
    print("status: ok")
    assert dashboard_response["recommendation"]["items"]
    full_result["dashboard"] = dashboard_response

    print("\n========== 6. Explanation 조회 ==========")
    explanation_response = get_explanation(project_id, match_id)
    print("GET /api/v1/projects/{id}/matches/{match_id}/explanation")
    print("overall_summary:", explanation_response["overall_summary"])
    assert explanation_response["overall_summary"]
    selected_provider = os.getenv("EXPLANATION_PROVIDER")
    if selected_provider == "azure_openai":
        assert explanation_response["provider"] == "azure_openai"
    explanation_text = explanation_response["overall_summary"] + " " + " ".join(
        [
            supplier["card_summary"]
            + " "
            + " ".join(supplier["strengths"])
            + " "
            + " ".join(supplier["weaknesses"])
            for supplier in explanation_response["supplier_explanations"]
        ]
    )
    assert "프로젝트명이 파일명 기준으로 보정됨" not in explanation_text
    assert "파일명 기준" not in explanation_text
    assert "후보 업체에 포함되지 않음" not in explanation_text
    assert "파트너 매칭 단계 미선정 업체" not in explanation_text
    assert "추천 리스트에 없던 업체" not in explanation_text
    for supplier in explanation_response["supplier_explanations"]:
        assert supplier["card_summary"].strip()
        assert not any(
            "가격 차이 5% 초과" in check
            for check in supplier["check_required"]
        )
    full_result["explanation"] = explanation_response

    print("\n========== 7. Compare 생성 ==========")
    compare_response = compare_quotes(
        project_id,
        CompareRequest(),
    )
    print("POST /api/v1/projects/{id}/compare")
    print("rows:", len(compare_response["rows"]))
    if compare_response["rows"]:
        first_row = compare_response["rows"][0]
        print("첫 번째 row 섹션 확인:")
        for section in [
            "company_info",
            "hardware",
            "cost_breakdown",
            "conditions",
            "total",
            "scores",
            "vendor_snapshot",
            "highlights",
        ]:
            print(f"{section}: {'ok' if section in first_row else 'missing'}")
    print("compare 주요 필드:")
    for row in compare_response["rows"]:
        print(
            row["vendor_name"],
            "age:",
            row["company_info"]["company_age_years"],
            "revenue_million:",
            row["company_info"]["avg_revenue_3y_million"],
            "avg_projects:",
            row["company_info"]["avg_project_count_3y"],
            "installation_count:",
            row["company_info"]["installation_count"],
            "screen:",
            row["hardware"]["screen_size_mm"],
            "pitch:",
            row["hardware"]["pixel_pitch"],
            "display_hw:",
            row["cost_breakdown"]["display_hw"]["amount"],
            "installation:",
            row["cost_breakdown"]["installation"]["status"],
            "delivery:",
            row["conditions"]["delivery"],
            "warranty:",
            row["conditions"]["warranty_display"],
            "total:",
            row["total"]["display_text"],
            "highlights:",
            row["highlights"],
    )
    assert compare_response["rows"]
    assert len(compare_response["rows"]) == quote_response["processed_count"]
    project_record = store.get_project(project_id)
    assert project_record is not None
    for row in compare_response["rows"]:
        assert "candidate_vendor_link" in row
        assert "company_location" in row
        assert row["vendor_snapshot"] is not None
        assert "company_location" in row["vendor_snapshot"]
        assert row["company_location"] == row["vendor_snapshot"]["company_location"]
        assert row["conditions"]["install_location"] == project_record.location
        if row["company_location"]:
            assert row["conditions"]["install_location"] != row["company_location"]
        assert "comparison_risks" in row
        assert not any("가격 차이 5% 초과" in item for item in row["check_required"])
        serialized_row = json.dumps(row, ensure_ascii=False)
        assert "후보 업체에 포함되지 않음" not in serialized_row
        assert "파트너 매칭 단계 미선정 업체" not in serialized_row
        assert "추천 리스트에 없던 업체" not in serialized_row
        price_warning = any(
            "가격 차이 5% 초과" in item for item in row.get("rule_warnings", [])
        )
        if price_warning:
            assert any(
                "가격 차이 5% 초과" in item
                for item in row["comparison_risks"]
            )
        conditions = row["conditions"]
        assert "payment_terms" in conditions
        joined_notes = " ".join(conditions["special_notes"])
        assert not any(
            token in joined_notes
            for token in [
                "합계 금액",
                "부가가치세",
                "전체 합 계",
                "공급가",
                "총 금액",
                "재질 : Steel",
                "해상도 :",
            ]
        )
        if conditions["payment_terms"]:
            assert conditions["payment_terms"] not in conditions["special_notes"]
    _validate_install_location_sources()
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
    print("\nFull API response JSON saved:", output_path)


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


def _validate_install_location_sources() -> None:
    class Result:
        metadata = {}
        parser_raw_matches = {}

    result = Result()
    assert _resolve_install_location(result, project_install_location=None) is None
    assert (
        _resolve_install_location(result, project_install_location="충북 음성")
        == "충북 음성"
    )

    result.metadata = {"install_location": "서울 강남 현장"}
    assert (
        _resolve_install_location(result, project_install_location=None)
        == "서울 강남 현장"
    )


def validate_compare_statuses(compare_response) -> None:
    statuses = collect_status_values(compare_response)
    print("compare status values:", sorted(set(statuses)))
    assert statuses
    assert all(status in ALLOWED_STATUSES for status in statuses)
    assert not any(status in KOREAN_STATUS_VALUES for status in statuses)

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
