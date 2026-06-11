import json

from services.api_demo.project_requirement_adapter import (
    build_requirement_info_from_project_payload,
)
from services.api_demo.routers import create_project, run_candidate_vendors
from services.api_demo.schemas import ProjectCreateRequest
from services.api_demo.store import store
from services.embedding.text_builder import build_requirement_embedding_text
from services.requirement_ingestion.factory import create_requirement_ingestion_pipeline


def _frontend_payload() -> ProjectCreateRequest:
    return ProjectCreateRequest(
        company_name="일강이앤아이",
        location="충북 음성",
        deadline="2026년 3월",
        request_text=(
            "프로젝트명: 충북 음성 회의실 디스플레이\n"
            "활용 용도: 회의실 태양광 발전 현황 확인\n"
            "디스플레이 크기: 3000x2000mm\n"
            "수량: 1식\n"
            "운영 시간: 업무시간 운영\n"
            "카테고리: LED전광판\n"
            "예산 상한: 3000만원\n"
            "현재 단계: 실시설계 단계\n"
            "우선 검토 기준: 가격 우선\n"
            "추가 요청사항: 실내 설치 필요\n"
            "첨부 메모: 없음"
        ),
    )


def test_frontend_payload_adapter() -> None:
    requirement = build_requirement_info_from_project_payload(
        _frontend_payload(),
        request_id="frontend_contract",
    )
    assert requirement.customer_name == "일강이앤아이"
    assert requirement.region == "충북 음성"
    assert requirement.install_schedule_text == "2026년 3월"
    assert requirement.project_name == "충북 음성 회의실 디스플레이"
    assert requirement.project_stage == "실시설계 단계"
    assert requirement.category == "LED전광판"
    assert requirement.display_size_text == "3000x2000mm"
    assert requirement.quantity_text == "1식"
    assert requirement.budget_max == 30000000
    assert requirement.operation_time == "업무시간 운영"
    assert requirement.review_preset == "가격 우선"
    assert requirement.other_conditions == "실내 설치 필요"
    assert requirement.attachment_memo is None
    assert requirement.products
    assert requirement.products[0].raw_text
    assert "LED전광판" in requirement.required_keywords
    assert requirement.metadata["source"] == "frontend_project_payload"
    assert requirement.metadata["review_preset"] == "가격 우선"


def test_placeholder_values_are_not_embedded_as_requirements() -> None:
    payload = ProjectCreateRequest(
        company_name="미입력",
        location=None,
        deadline=None,
        request_text=(
            "프로젝트명: 미입력\n"
            "활용 용도: 미입력\n"
            "디스플레이 크기: 미입력\n"
            "수량: 미입력\n"
            "운영 시간: 미입력\n"
            "카테고리: 미입력\n"
            "예산 상한: 미입력\n"
            "현재 단계: 미입력\n"
            "우선 검토 기준: 미입력\n"
            "추가 요청사항: 없음\n"
            "첨부 메모: 없음"
        ),
    )
    requirement = build_requirement_info_from_project_payload(payload)
    embedding_text = build_requirement_embedding_text(requirement)
    assert requirement.customer_name is None
    assert requirement.products == []
    assert requirement.required_keywords == ["디스플레이", "설치"]
    assert "미입력" not in embedding_text
    assert "없음" not in embedding_text
    assert requirement.metadata["original_request_text"]


def test_process_requirement_info_does_not_use_parser() -> None:
    pipeline = create_requirement_ingestion_pipeline()
    requirement = build_requirement_info_from_project_payload(
        _frontend_payload(),
        request_id="frontend_contract",
    )
    result = pipeline.process_requirement_info(
        requirement,
        request_id="frontend_contract",
    )
    assert result.metadata["requirement_source"] == "frontend_project_payload"
    assert result.metadata["parser_provider"] is None
    assert result.parser_warnings == []
    assert result.embedding_dim is None or result.embedding_dim > 0
    assert "일강이앤아이" in result.embedding_text
    assert "충북 음성" in result.embedding_text
    assert "2026년 3월" in result.embedding_text
    assert "LED전광판" in result.embedding_text
    assert "3000x2000mm" in result.embedding_text
    assert "30000000원" in result.embedding_text


def test_project_create_and_candidate_vendors_reuse_project_requirement() -> None:
    project_response = create_project(_frontend_payload())
    project_id = project_response["project_id"]
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

    candidate_response = run_candidate_vendors(project_id, payload=None)
    assert candidate_response["ok"] is True
    assert candidate_response["data"]["candidate_vendors"]
    assert candidate_response["data"]["selected_vendor_names"]
    assert "embedding_vector" not in json.dumps(candidate_response, ensure_ascii=False)


def main() -> None:
    test_frontend_payload_adapter()
    test_placeholder_values_are_not_embedded_as_requirements()
    test_process_requirement_info_does_not_use_parser()
    test_project_create_and_candidate_vendors_reuse_project_requirement()
    print("frontend project payload contract tests passed")


if __name__ == "__main__":
    main()
