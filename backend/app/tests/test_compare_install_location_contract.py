import json
from pathlib import Path

from config.paths import DATA_DIR
from services.api_demo.routers import (
    compare_quotes,
    create_project,
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


def _frontend_request_text() -> str:
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


def _demo_file_paths(limit: int = 4) -> list[Path]:
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


def _create_project(location: str | None):
    return create_project(
        ProjectCreateRequest(
            company_name="일강이앤아이",
            location=location,
            deadline="2026년 3월",
            request_text=_frontend_request_text(),
        )
    )


def _run_compare(project_id: str, file_paths: list[Path]) -> dict:
    quote_response = upload_quote_paths(project_id, file_paths)
    assert quote_response["processed_count"] > 0
    run_match(project_id, MatchRunRequest(quote_top_n=3, run_explanation=False))
    compare_response = compare_quotes(project_id, CompareRequest())
    assert len(compare_response["rows"]) == quote_response["processed_count"]
    return compare_response


def test_compare_rows_use_project_requirement_region() -> None:
    file_paths = _demo_file_paths()
    if not file_paths:
        print("demo quote files not found; skipping install_location contract check")
        return

    project = _create_project("충북 음성")
    run_candidate_vendors(
        project["project_id"],
        CandidateVendorsRequest(top_n=10, similarity_threshold=0.0),
    )
    compare_response = _run_compare(project["project_id"], file_paths)

    selected_count = 0
    non_selected_count = 0
    for row in compare_response["rows"]:
        assert row.get("install_location") == "충북 음성"
        assert row.get("conditions", {}).get("install_location") == "충북 음성"
        assert row.get("company_location") != row.get("install_location")

        link = row.get("candidate_vendor_link") or {}
        if link.get("is_selected_vendor") is True:
            selected_count += 1
        elif link.get("is_selected_vendor") is False:
            non_selected_count += 1

    assert selected_count > 0
    assert non_selected_count > 0


def test_compare_rows_do_not_fallback_to_company_location() -> None:
    file_paths = _demo_file_paths(limit=2)
    if not file_paths:
        print("demo quote files not found; skipping empty install_location check")
        return

    project = _create_project(None)
    compare_response = _run_compare(project["project_id"], file_paths)

    for row in compare_response["rows"]:
        assert row.get("install_location") is None
        assert row.get("conditions", {}).get("install_location") is None
        assert "company_location" in row

    assert "embedding_vector" not in json.dumps(compare_response, ensure_ascii=False)


def main() -> None:
    test_compare_rows_use_project_requirement_region()
    test_compare_rows_do_not_fallback_to_company_location()
    print("compare install_location contract tests passed")


if __name__ == "__main__":
    main()
