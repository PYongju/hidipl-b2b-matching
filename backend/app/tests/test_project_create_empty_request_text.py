from __future__ import annotations

import asyncio
from unittest.mock import patch

from fastapi import HTTPException

from api.v1.routes import (
    ProjectCreateRequest as ApiProjectCreateRequest,
    create_project as api_create_project,
)
from services.api_demo import routers as demo_routers
from services.api_demo.project_requirement_adapter import is_frontend_project_payload
from services.api_demo.schemas import CandidateVendorsRequest, ProjectCreateRequest
from services.api_demo.store import ApiDemoStore
from services.requirement.schemas import RequirementInfo
from services.requirement_ingestion.factory import create_requirement_ingestion_pipeline
from services.requirement_ingestion.schemas import RequirementIngestionResult


class FakeRequirementPipeline:
    def __init__(self) -> None:
        self.process_text_calls = 0
        self.process_requirement_info_calls = 0

    def process_text(
        self,
        request_text: str,
        *,
        request_id: str | None = None,
    ) -> RequirementIngestionResult:
        self.process_text_calls += 1
        raise AssertionError(f"process_text must not be called, got {request_text!r}")

    def process_requirement_info(
        self,
        requirement: RequirementInfo,
        *,
        request_id: str | None = None,
    ) -> RequirementIngestionResult:
        self.process_requirement_info_calls += 1
        return RequirementIngestionResult(
            request_id=request_id,
            source_type="structured",
            source_path=None,
            requirement=requirement,
            embedding_text="structured requirement embedding text",
            embedding_vector=None,
            embedding_dim=3,
            raw_text_preview=requirement.raw_text[:200],
            parser_warnings=[],
            ingestion_warnings=[],
            metadata={
                "requirement_source": "frontend_project_payload",
                "parser_provider": None,
            },
        )


class FakeDbSession:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    def execute(self, *args, **kwargs):
        self.execute_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_completely_empty_project_request_creates_shell() -> None:
    payload = ProjectCreateRequest(
        company_name="",
        location=None,
        deadline=None,
        request_text="",
    )
    fake_pipeline = FakeRequirementPipeline()
    fake_store = ApiDemoStore(persistence=None)

    with (
        patch.object(demo_routers, "store", fake_store),
        patch.object(
            demo_routers,
            "create_requirement_ingestion_pipeline",
            return_value=fake_pipeline,
        ),
    ):
        response = demo_routers.create_project(payload)

    project_id = response["project_id"]
    record = fake_store.get_project(project_id)
    assert record is not None
    assert record.requirement_result is None
    assert record.requirement_source == "empty_project_shell"
    assert project_id in fake_store.lazy_hydration_project_ids
    assert fake_pipeline.process_text_calls == 0
    assert fake_pipeline.process_requirement_info_calls == 0
    assert response["request_id"]
    assert response["customer_name"] is None
    assert response["products"] == []
    assert response["embedding_dim"] is None
    assert response["ingestion_warnings"] == [
        "프로젝트 요구사항이 아직 입력되지 않았습니다."
    ]
    assert "embedding_vector" not in response


def test_placeholder_only_project_request_creates_shell() -> None:
    payload = ProjectCreateRequest(
        company_name="미입력",
        location=None,
        deadline=None,
        request_text="",
    )
    fake_pipeline = FakeRequirementPipeline()
    fake_store = ApiDemoStore(persistence=None)

    with (
        patch.object(demo_routers, "store", fake_store),
        patch.object(
            demo_routers,
            "create_requirement_ingestion_pipeline",
            return_value=fake_pipeline,
        ),
    ):
        response = demo_routers.create_project(payload)

    record = fake_store.get_project(response["project_id"])
    assert record is not None
    assert record.requirement_result is None
    assert response["embedding_dim"] is None
    assert response["project_id"] in fake_store.lazy_hydration_project_ids
    assert fake_pipeline.process_text_calls == 0
    assert fake_pipeline.process_requirement_info_calls == 0


def test_placeholder_only_frontend_label_payload_creates_shell() -> None:
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
    fake_pipeline = FakeRequirementPipeline()
    fake_store = ApiDemoStore(persistence=None)

    with (
        patch.object(demo_routers, "store", fake_store),
        patch.object(
            demo_routers,
            "create_requirement_ingestion_pipeline",
            return_value=fake_pipeline,
        ),
    ):
        response = demo_routers.create_project(payload)

    record = fake_store.get_project(response["project_id"])
    assert record is not None
    assert record.requirement_result is None
    assert response["embedding_dim"] is None
    assert response["project_id"] in fake_store.lazy_hydration_project_ids
    assert fake_pipeline.process_text_calls == 0
    assert fake_pipeline.process_requirement_info_calls == 0


def test_structured_scalar_empty_request_text_uses_adapter() -> None:
    payload = ProjectCreateRequest(
        company_name="일강이엔아이",
        location="충북 음성",
        deadline="2026년 3월",
        request_text="",
    )
    fake_pipeline = FakeRequirementPipeline()
    fake_store = ApiDemoStore(persistence=None)

    with (
        patch.object(demo_routers, "store", fake_store),
        patch.object(
            demo_routers,
            "create_requirement_ingestion_pipeline",
            return_value=fake_pipeline,
        ),
    ):
        response = demo_routers.create_project(payload)

    record = fake_store.get_project(response["project_id"])
    assert record is not None
    assert record.requirement_result is not None
    assert response["project_id"] not in fake_store.lazy_hydration_project_ids
    assert fake_pipeline.process_text_calls == 0
    assert fake_pipeline.process_requirement_info_calls == 1
    assert response["customer_name"] == "일강이엔아이"
    assert response["region"] == "충북 음성"
    assert response["install_schedule_text"] == "2026년 3월"
    assert response["embedding_dim"] == 3
    assert "embedding_vector" not in response


def test_frontend_labels_use_adapter_without_structured_scalar() -> None:
    payload = ProjectCreateRequest(
        company_name="",
        location=None,
        deadline=None,
        request_text="프로젝트명: 테스트 프로젝트\n카테고리: LED전광판",
    )
    fake_pipeline = FakeRequirementPipeline()
    fake_store = ApiDemoStore(persistence=None)

    assert is_frontend_project_payload(payload) is True
    with (
        patch.object(demo_routers, "store", fake_store),
        patch.object(
            demo_routers,
            "create_requirement_ingestion_pipeline",
            return_value=fake_pipeline,
        ),
    ):
        response = demo_routers.create_project(payload)

    assert fake_pipeline.process_text_calls == 0
    assert fake_pipeline.process_requirement_info_calls == 1
    assert response["products"]


def test_empty_project_candidate_vendors_returns_skipped_response() -> None:
    fake_store = ApiDemoStore(persistence=None)
    with patch.object(demo_routers, "store", fake_store):
        response = demo_routers.create_project(ProjectCreateRequest())
        candidate_response = demo_routers.run_candidate_vendors(
            response["project_id"],
            CandidateVendorsRequest(),
        )

    assert candidate_response["ok"] is True
    data = candidate_response["data"]
    assert data["status"] == "requirement_required"
    assert data["candidate_vendors"] == []
    assert data["selected_vendor_names"] == []
    assert data["metadata"]["candidate_vendors_skipped"] is True
    assert data["metadata"]["embedding_executed"] is False
    assert data["metadata"]["partner_matching_executed"] is False


def test_api_project_create_accepts_empty_body() -> None:
    body = ApiProjectCreateRequest()
    db = FakeDbSession()
    fake_store = ApiDemoStore(persistence=None)

    with patch.object(demo_routers, "store", fake_store):
        response = asyncio.run(api_create_project(body, db=db))

    assert response["ok"] is True
    data = response["data"]
    assert data["project_id"]
    assert data["embedding_dim"] is None
    assert data["products"] == []
    assert db.execute_calls == 1
    assert db.commit_calls == 1
    assert db.rollback_calls == 0


def test_process_text_empty_validation_is_preserved() -> None:
    pipeline = create_requirement_ingestion_pipeline()
    try:
        pipeline.process_text("")
    except ValueError as exc:
        assert "고객 요청 텍스트가 비어 있습니다" in str(exc)
    else:
        raise AssertionError("process_text('') must keep raising ValueError")


def main() -> None:
    test_completely_empty_project_request_creates_shell()
    test_placeholder_only_project_request_creates_shell()
    test_placeholder_only_frontend_label_payload_creates_shell()
    test_structured_scalar_empty_request_text_uses_adapter()
    test_frontend_labels_use_adapter_without_structured_scalar()
    test_empty_project_candidate_vendors_returns_skipped_response()
    test_api_project_create_accepts_empty_body()
    test_process_text_empty_validation_is_preserved()
    print("project create empty request_text tests passed")


if __name__ == "__main__":
    main()
