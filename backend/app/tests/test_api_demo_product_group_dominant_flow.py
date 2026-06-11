import json
from pathlib import Path

from config.paths import DATA_DIR, OUTPUT_DIR
from services.api_demo.response_builders import strip_heavy_fields
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
from services.recommendation.product_group_filter import resolve_requirement_product_groups
from services.api_demo.store import store


OUTPUT_PATH = OUTPUT_DIR / "api_demo_compare_response_dominant_product_group.json"


def ambiguous_request_text() -> str:
    return "\n".join(
        [
            "프로젝트명: 충북 음성 회의실 디스플레이",
            "활용 용도: 회의실 화면 표시 장비 검토",
            "디스플레이 크기: 미입력",
            "수량: 미입력",
            "운영 시간: 업무시간 운영",
            "카테고리: 디스플레이",
            "예산 상한: 미입력",
            "현재 단계: 실시설계 단계",
            "우선 검토 기준: 가격 우선",
            "추가 요청사항: 회의실용 디스플레이 설치",
            "첨부 메모: 없음",
        ]
    )


def data_quote_files() -> list[Path]:
    names = [
        "일강_비디오월&LED전광판(p1_5)_효성itx.pdf",
        "일강_비디오월_46인치_다올씨앤씨.pdf",
        "일강_비디오월_49인치_딥사이닝.pdf",
        "일강_비디오월_55인치_다올씨앤씨_3안_삼성전자.pdf",
        "일강_비디오월_55인치_다올씨앤씨_4안_다올씨앤씨LCD.pdf",
        "일강_비디오월_55인치_딥사이닝.pdf",
        "일강_비디오월_55인치_시스메이트.pdf",
    ]
    paths = [DATA_DIR / name for name in names]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise AssertionError("missing demo quote files: " + ", ".join(missing))
    return paths


def main() -> None:
    project = create_project(
        ProjectCreateRequest(
            company_name="일강이앤아이",
            location="충북 음성",
            deadline="2026년 3월",
            request_text=ambiguous_request_text(),
        )
    )
    project_id = project["project_id"]
    project_record = store.get_project(project_id)
    assert project_record is not None
    requirement = project_record.requirement_result.requirement
    assert resolve_requirement_product_groups(requirement) == set()

    candidate_response = run_candidate_vendors(
        project_id,
        CandidateVendorsRequest(top_n=10, similarity_threshold=0.0),
    )
    assert candidate_response["ok"] is True
    assert "embedding_vector" not in json.dumps(candidate_response, ensure_ascii=False)

    quote_response = upload_quote_paths(project_id, data_quote_files())
    assert quote_response["processed_count"] >= 8

    match_response = run_match(
        project_id,
        MatchRunRequest(quote_top_n=3, run_explanation=False),
    )
    recommendation = match_response["recommendation"]
    product_filter = recommendation["metadata"]["product_group_filter"]
    excluded = recommendation["metadata"]["product_group_excluded_candidates"]

    assert product_filter["source"] == "quote_pool_dominant_group"
    assert product_filter["selected_product_groups"] == ["비디오월"]
    assert product_filter["requirement_product_groups"] == []
    assert product_filter["quote_product_group_counts"]["비디오월"] > product_filter["quote_product_group_counts"]["LED전광판"]
    assert product_filter["input_quote_count"] == quote_response["processed_count"]
    assert product_filter["ranking_quote_count"] >= 3
    assert product_filter["excluded_quote_count"] >= 1
    assert product_filter["selection_required"] is False
    assert product_filter["fallback_used"] is False
    assert len(recommendation["items"]) == 3
    assert all(
        "비디오월"
        in product_filter["quote_product_groups_by_quote_id"].get(item["quote_id"], [])
        for item in recommendation["items"]
    )
    assert any(
        "효성ITX" in candidate["quote_id"]
        and "LED전광판" in candidate["quote_id"]
        and candidate["quote_product_groups"] == ["LED전광판"]
        for candidate in excluded
    )
    assert any(
        "효성ITX" in item["quote_id"]
        and "비디오월" in product_filter["quote_product_groups_by_quote_id"].get(item["quote_id"], [])
        for item in recommendation["all_items"]
    )

    compare_response = compare_quotes(project_id, CompareRequest())
    compare_filter = compare_response["metadata"]["product_group_filter"]
    assert compare_filter["source"] == "quote_pool_dominant_group"
    assert compare_filter["selected_product_groups"] == ["비디오월"]
    assert len(compare_response["rows"]) == compare_filter["ranking_quote_count"]
    assert len(compare_response["rows"]) >= 3
    for row in compare_response["rows"]:
        groups = compare_filter["quote_product_groups_by_quote_id"].get(row["quote_id"], [])
        assert "비디오월" in groups
        assert "LED전광판" not in groups
    assert any(
        "효성ITX" in candidate["quote_id"]
        and candidate["option_label"] == "LED전광판"
        for candidate in compare_response["metadata"]["excluded_candidates"]
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(strip_heavy_fields(compare_response), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    text = OUTPUT_PATH.read_text(encoding="utf-8")
    assert "embedding_vector" not in text
    assert "api_key" not in text.lower()
    assert "ocr_full_text" not in text
    assert "ocr_text" not in text
    assert "C:\\" not in text
    assert "/Users/" not in text
    print("dominant product group API flow test passed")
    print("compare response saved:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
