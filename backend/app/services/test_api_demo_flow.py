import json
from pathlib import Path
from pprint import pprint

from config.paths import DATA_DIR, OUTPUT_DIR
from services.api_demo.response_builders import strip_heavy_fields
from services.api_demo.routers import (
    compare_quotes,
    create_project,
    get_explanation,
    get_matches,
    run_match,
    upload_quote_paths,
)
from services.api_demo.schemas import CompareRequest, MatchRunRequest, ProjectCreateRequest


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

    print("\n========== 2. Quote Pool 생성 ==========")
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
        )
    assert quote_response["processed_count"] > 0
    full_result["quote_upload"] = quote_response

    print("\n========== 3. Match 실행 ==========")
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
    full_result["match_run"] = match_response

    print("\n========== 4. Dashboard 조회 ==========")
    dashboard_response = get_matches(project_id)
    print("GET /api/v1/projects/{id}/matches")
    print("status: ok")
    assert dashboard_response["recommendation"]["items"]
    full_result["dashboard"] = dashboard_response

    print("\n========== 5. Explanation 조회 ==========")
    explanation_response = get_explanation(project_id, match_id)
    print("GET /api/v1/projects/{id}/matches/{match_id}/explanation")
    print("overall_summary:", explanation_response["overall_summary"])
    assert explanation_response["overall_summary"]
    full_result["explanation"] = explanation_response

    print("\n========== 6. Compare 생성 ==========")
    compare_response = compare_quotes(
        project_id,
        CompareRequest(top_n=3),
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


if __name__ == "__main__":
    main()
