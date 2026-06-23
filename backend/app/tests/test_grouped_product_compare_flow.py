import json
import os
from pathlib import Path

from config.paths import DATA_DIR, OUTPUT_DIR
from services.api_demo.response_builders import strip_heavy_fields
from services.api_demo.routers import (
    compare_quotes,
    create_project,
    get_matches,
    run_match,
    upload_quote_paths,
)
from services.api_demo.schemas import CompareRequest, MatchRunRequest, ProjectCreateRequest
from services.recommendation.product_group_filter import group_quotes_by_product_group
from services.api_demo.store import store


GROUPED_MATCH_OUTPUT_PATH = OUTPUT_DIR / "api_demo_grouped_match_response.json"
GROUPED_COMPARE_OUTPUT_PATH = OUTPUT_DIR / "api_demo_grouped_compare_response.json"


def main() -> None:
    os.environ.setdefault("QUOTE_PARSER_PROVIDER", "rule")
    os.environ.setdefault("ENABLE_LEGACY_SAMPLE_PATCHES", "false")
    test_grouped_product_compare_flow_on_data_quotes()
    print("grouped product compare flow tests passed")


def test_grouped_product_compare_flow_on_data_quotes() -> None:
    project_response = create_project(
        ProjectCreateRequest(
            company_name="일강이앤아이",
            location="충북 음성",
            deadline="2026년 3월",
            request_text="\n".join(
                [
                    "프로젝트명: 충북 음성 회의실 디스플레이",
                    "활용 용도: 회의실 디스플레이 설치 검토",
                    "디스플레이 크기: 미입력",
                    "수량: 1식",
                    "운영 시간: 업무시간 운영",
                    "카테고리: 디스플레이",
                    "예산 상한: 3000만원",
                    "현재 단계: 실시설계 단계",
                    "우선 검토 기준: 가격 우선",
                    "추가 요청사항: 회의실용 디스플레이 설치",
                    "첨부 메모: 없음",
                ]
            ),
        )
    )
    project_id = project_response["project_id"]

    quote_response = upload_quote_paths(project_id, find_data_quote_files())
    assert quote_response["processed_count"] == 12

    quote_pool = store.get_quote_pool(project_id)
    assert quote_pool is not None
    groups = group_quotes_by_product_group(quote_pool.quote_ingestion_results)
    assert len(groups["LED전광판"]) == 5
    assert len(groups["비디오월"]) == 7

    match_response = run_match(
        project_id,
        MatchRunRequest(
            quote_top_n=3,
            run_explanation=True,
            explanation_provider="template",
        ),
    )
    assert match_response["match_id"]
    assert match_response["metadata"]["grouped_by_product_group"] is True
    assert match_response["metadata"]["product_group_counts"]["LED전광판"] == 5
    assert match_response["metadata"]["product_group_counts"]["비디오월"] == 7

    recommendation_groups = match_response["recommendation_groups"]
    assert {group["product_group"] for group in recommendation_groups} == {
        "LED전광판",
        "비디오월",
    }
    for group in recommendation_groups:
        recommendation = group["recommendation"]
        assert len(recommendation["items"]) <= 3
        assert len(recommendation["all_items"]) == group["quote_count"]
        assert [item["rank"] for item in recommendation["items"]] == list(
            range(1, len(recommendation["items"]) + 1)
        )
        assert group["explanation"] is not None

    dashboard_response = get_matches(project_id)
    assert dashboard_response["match_id"] == match_response["match_id"]
    assert len(dashboard_response["recommendation_groups"]) == 2

    video_dashboard_response = get_matches(project_id, product_group="비디오월")
    assert len(video_dashboard_response["recommendation_groups"]) == 1
    assert video_dashboard_response["recommendation_groups"][0]["product_group"] == "비디오월"

    compare_response = compare_quotes(project_id, CompareRequest())
    assert compare_response["metadata"]["grouped_by_product_group"] is True
    assert compare_response["metadata"]["product_group_counts"]["LED전광판"] == 5
    assert compare_response["metadata"]["product_group_counts"]["비디오월"] == 7
    assert len(compare_response["groups"]) == 2
    assert len(compare_response["rows"]) == 12
    group_rows = {group["product_group"]: group["rows"] for group in compare_response["groups"]}
    assert len(group_rows["LED전광판"]) == 5
    assert len(group_rows["비디오월"]) == 7
    assert all(row["product_group"] == "LED전광판" for row in group_rows["LED전광판"])
    assert all(row["product_group"] == "비디오월" for row in group_rows["비디오월"])

    video_compare_response = compare_quotes(
        project_id,
        CompareRequest(),
        product_group="비디오월",
    )
    assert len(video_compare_response["groups"]) == 1
    assert video_compare_response["groups"][0]["product_group"] == "비디오월"
    assert all(row["product_group"] == "비디오월" for row in video_compare_response["rows"])

    write_json(GROUPED_MATCH_OUTPUT_PATH, match_response)
    write_json(GROUPED_COMPARE_OUTPUT_PATH, compare_response)


def find_data_quote_files() -> list[Path]:
    files = [
        path
        for path in sorted(DATA_DIR.iterdir())
        if path.suffix.lower() in {".pdf", ".xlsx", ".png", ".jpg", ".jpeg"}
        and path.name.startswith("일강_")
    ]
    assert len(files) == 11
    return files


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_sanitize_for_output(value), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _sanitize_for_output(value):
    value = strip_heavy_fields(value)
    if isinstance(value, dict):
        return {key: _sanitize_for_output(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_output(item) for item in value]
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        if "/uploads/" in normalized or "/data/" in normalized:
            return normalized.rsplit("/", 1)[-1]
    return value


if __name__ == "__main__":
    main()
