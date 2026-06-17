from __future__ import annotations

from unittest.mock import patch

from services.api_demo import routers as demo_routers
from services.api_demo.schemas import CandidateVendorsRequest, ProjectCreateRequest
from services.api_demo.store import ApiDemoStore
from services.api_demo.store_persistence import FakeJsonApiDemoPersistence
from services.partner_matching.schemas import (
    PartnerMatchCandidate,
    PartnerMatchingResult,
)
from services.requirement.schemas import RequirementInfo
from services.requirement_ingestion.schemas import RequirementIngestionResult


class FakeRequirementPipeline:
    def __init__(self) -> None:
        self.process_requirement_info_calls = 0

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
            embedding_text="hydrated requirement embedding text",
            embedding_vector=[0.1, 0.2, 0.3],
            embedding_dim=3,
            raw_text_preview=requirement.raw_text[:200],
            parser_warnings=[],
            ingestion_warnings=[],
            metadata={
                "requirement_source": "frontend_project_payload",
                "parser_provider": None,
            },
        )


class FakePartnerMatchingPipeline:
    def __init__(self) -> None:
        self.run_calls = 0

    def run(
        self,
        requirement_result: RequirementIngestionResult,
        *,
        top_n: int,
        similarity_threshold: float,
    ) -> PartnerMatchingResult:
        self.run_calls += 1
        candidates = [
            PartnerMatchCandidate(
                partner_name="테스트파트너",
                specialty_tags=["LED전광판"],
                semantic_similarity_score=90.0,
                cosine_similarity=0.9,
                is_premium=False,
                success_rate=0.1,
                response_speed="normal",
                financial_status="normal",
                is_excluded=False,
                business_rule_passed=True,
                business_stage="selected_top_n",
                filter_reasons=[],
                check_required=[],
                sort_key=[],
                rank=1,
                company_location="서울",
                installation_count=3,
                final_score=90.0,
                semantic_score_calibrated=90.0,
                specialty_match_score=100.0,
                score_breakdown={"semantic_score": 90.0},
            )
        ]
        return PartnerMatchingResult(
            request_id=requirement_result.request_id,
            customer_name=requirement_result.requirement.customer_name,
            top_n=top_n,
            candidates=candidates,
            all_candidates=candidates,
            filtered_candidates=[],
            metadata={"provider": "FakePartnerMatchingPipeline"},
        )


def test_empty_shell_db_project_scalar_hydrates_and_runs_candidate_vendors() -> None:
    persistence = FakeJsonApiDemoPersistence()
    store = ApiDemoStore(persistence=persistence)
    requirement_pipeline = FakeRequirementPipeline()
    matching_pipeline = FakePartnerMatchingPipeline()

    with (
        patch.object(demo_routers, "store", store),
        patch.object(
            demo_routers,
            "create_requirement_ingestion_pipeline",
            return_value=requirement_pipeline,
        ),
        patch.object(
            demo_routers,
            "create_partner_matching_pipeline",
            return_value=matching_pipeline,
        ),
    ):
        created = demo_routers.create_project(ProjectCreateRequest())
        project_id = created["project_id"]
        persistence.projects[project_id].update(
            {
                "company_name": "일강이엔아이",
                "location": "충북 음성",
                "deadline": "3개월 내외",
                "request_text": "회의실 내 태양광 발전 현황 확인을 위한 비디오월 또는 LED 전광판 검토",
            }
        )
        response = demo_routers.run_candidate_vendors(
            project_id,
            CandidateVendorsRequest(top_n=10),
        )

    assert response["ok"] is True
    data = response["data"]
    assert data.get("status") != "requirement_required"
    assert data["candidate_vendors"]
    assert data["selected_vendor_names"] == ["테스트파트너"]
    assert data["metadata"]["lazy_hydration_used"] is True
    assert requirement_pipeline.process_requirement_info_calls == 1
    assert matching_pipeline.run_calls == 1
    assert store.get_project(project_id).requirement_result is not None
    assert project_id not in store.lazy_hydration_project_ids
    assert persistence.projects[project_id]["requirement_result"] is not None


def test_empty_shell_without_scalar_returns_requirement_required() -> None:
    store = ApiDemoStore(persistence=FakeJsonApiDemoPersistence())
    requirement_pipeline = FakeRequirementPipeline()
    matching_pipeline = FakePartnerMatchingPipeline()

    with (
        patch.object(demo_routers, "store", store),
        patch.object(
            demo_routers,
            "create_requirement_ingestion_pipeline",
            return_value=requirement_pipeline,
        ),
        patch.object(
            demo_routers,
            "create_partner_matching_pipeline",
            return_value=matching_pipeline,
        ),
    ):
        created = demo_routers.create_project(ProjectCreateRequest())
        response = demo_routers.run_candidate_vendors(
            created["project_id"],
            CandidateVendorsRequest(top_n=10),
        )

    assert response["ok"] is True
    assert response["data"]["status"] == "requirement_required"
    assert response["data"]["candidate_vendors"] == []
    assert response["data"]["metadata"]["embedding_executed"] is False
    assert response["data"]["metadata"]["partner_matching_executed"] is False
    assert requirement_pipeline.process_requirement_info_calls == 0
    assert matching_pipeline.run_calls == 0


def test_memory_project_scalar_hydrates_and_runs_candidate_vendors() -> None:
    store = ApiDemoStore(persistence=None)
    requirement_pipeline = FakeRequirementPipeline()
    matching_pipeline = FakePartnerMatchingPipeline()

    with (
        patch.object(demo_routers, "store", store),
        patch.object(
            demo_routers,
            "create_requirement_ingestion_pipeline",
            return_value=requirement_pipeline,
        ),
        patch.object(
            demo_routers,
            "create_partner_matching_pipeline",
            return_value=matching_pipeline,
        ),
    ):
        created = demo_routers.create_project(
            ProjectCreateRequest(
                company_name="일강이엔아이",
                location="충북 음성",
                deadline="3개월 내외",
                request_text="",
            )
        )
        project = store.get_project(created["project_id"])
        project.requirement_result = None
        store.lazy_hydration_project_ids.add(project.project_id)
        requirement_pipeline.process_requirement_info_calls = 0
        response = demo_routers.run_candidate_vendors(
            project.project_id,
            CandidateVendorsRequest(top_n=10),
        )

    assert response["data"]["candidate_vendors"]
    assert response["data"]["metadata"]["lazy_hydration_used"] is True
    assert requirement_pipeline.process_requirement_info_calls == 1
    assert matching_pipeline.run_calls == 1


def test_existing_requirement_result_is_reused_without_hydration() -> None:
    store = ApiDemoStore(persistence=None)
    requirement_pipeline = FakeRequirementPipeline()
    matching_pipeline = FakePartnerMatchingPipeline()

    with (
        patch.object(demo_routers, "store", store),
        patch.object(
            demo_routers,
            "create_requirement_ingestion_pipeline",
            return_value=requirement_pipeline,
        ),
        patch.object(
            demo_routers,
            "create_partner_matching_pipeline",
            return_value=matching_pipeline,
        ),
    ):
        created = demo_routers.create_project(
            ProjectCreateRequest(
                company_name="일강이엔아이",
                location="충북 음성",
                deadline="3개월 내외",
                request_text="",
            )
        )
        requirement_pipeline.process_requirement_info_calls = 0
        response = demo_routers.run_candidate_vendors(
            created["project_id"],
            CandidateVendorsRequest(top_n=10),
        )

    assert response["data"]["candidate_vendors"]
    assert response["data"]["metadata"]["lazy_hydration_used"] is False
    assert requirement_pipeline.process_requirement_info_calls == 0
    assert matching_pipeline.run_calls == 1


def test_placeholder_only_project_scalar_remains_skipped() -> None:
    persistence = FakeJsonApiDemoPersistence()
    store = ApiDemoStore(persistence=persistence)
    requirement_pipeline = FakeRequirementPipeline()
    matching_pipeline = FakePartnerMatchingPipeline()

    with (
        patch.object(demo_routers, "store", store),
        patch.object(
            demo_routers,
            "create_requirement_ingestion_pipeline",
            return_value=requirement_pipeline,
        ),
        patch.object(
            demo_routers,
            "create_partner_matching_pipeline",
            return_value=matching_pipeline,
        ),
    ):
        created = demo_routers.create_project(
            ProjectCreateRequest(
                company_name="미입력",
                location=None,
                deadline=None,
                request_text=(
                    "프로젝트명: 미입력\n"
                    "카테고리: 미입력\n"
                    "추가 요청사항: 없음"
                ),
            )
        )
        response = demo_routers.run_candidate_vendors(
            created["project_id"],
            CandidateVendorsRequest(top_n=10),
        )

    assert response["data"]["status"] == "requirement_required"
    assert response["data"]["candidate_vendors"] == []
    assert requirement_pipeline.process_requirement_info_calls == 0
    assert matching_pipeline.run_calls == 0


def main() -> None:
    test_empty_shell_db_project_scalar_hydrates_and_runs_candidate_vendors()
    test_empty_shell_without_scalar_returns_requirement_required()
    test_memory_project_scalar_hydrates_and_runs_candidate_vendors()
    test_existing_requirement_result_is_reused_without_hydration()
    test_placeholder_only_project_scalar_remains_skipped()
    print("candidate vendors lazy hydration tests passed")


if __name__ == "__main__":
    main()
