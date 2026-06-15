from __future__ import annotations

from datetime import datetime

from services.api_demo import routers as demo_routers
from services.api_demo.schemas import CandidateVendorsRequest
from services.api_demo.store import ApiDemoStore, ProjectRecord
from services.api_demo.store_bootstrap import bootstrap_api_demo_store_from_persistence
from services.api_demo.store_persistence import FakeJsonApiDemoPersistence
from services.partner_matching.schemas import PartnerMatchCandidate, PartnerMatchingResult
from services.requirement.schemas import RequirementInfo, RequirementProduct
from services.requirement_ingestion.schemas import RequirementIngestionResult


def main() -> None:
    test_bootstrap_does_not_hydrate_missing_requirement()
    test_candidate_vendors_hydrates_only_one_missing_project()
    test_bootstrap_with_10_projects_does_not_call_embedding()
    test_existing_requirement_result_json_is_reused()
    print("API demo store bootstrap tests passed")


def test_bootstrap_does_not_hydrate_missing_requirement() -> None:
    persistence = FakeJsonApiDemoPersistence()
    with_requirement = _project_record("project_with_req", _requirement_result("request_with_req"))
    without_requirement = _project_record("project_missing_req", None)
    persistence.save_project_record(with_requirement)
    persistence.save_project_record(without_requirement)

    store = ApiDemoStore(persistence=persistence)
    result = bootstrap_api_demo_store_from_persistence(store)

    assert result["azure_calls"] == 0
    assert result["loaded_projects"] == 2
    assert result["loaded_projects_with_requirement_result"] == 1
    assert result["lazy_hydration_projects"] == 1
    assert store.get_project("project_with_req").requirement_result is not None
    assert store.get_project("project_missing_req").requirement_result is None
    assert "project_missing_req" in store.lazy_hydration_project_ids


def test_candidate_vendors_hydrates_only_one_missing_project() -> None:
    persistence = FakeJsonApiDemoPersistence()
    persistence.save_project_record(_project_record("project_a", None))
    persistence.save_project_record(_project_record("project_b", None))
    store = ApiDemoStore(persistence=persistence)
    bootstrap_api_demo_store_from_persistence(store)

    calls = {"hydration": 0}
    with _patched_demo_routers(store, calls):
        response = demo_routers.run_candidate_vendors(
            "project_a",
            CandidateVendorsRequest(top_n=1, similarity_threshold=0.0),
        )

    assert response["ok"] is True
    assert calls["hydration"] == 1
    assert store.get_project("project_a").requirement_result is not None
    assert store.get_project("project_b").requirement_result is None
    assert "project_a" not in store.lazy_hydration_project_ids
    assert "project_b" in store.lazy_hydration_project_ids
    assert persistence.projects["project_a"]["requirement_result"] is not None
    assert persistence.projects["project_b"]["requirement_result"] is None


def test_bootstrap_with_10_projects_does_not_call_embedding() -> None:
    persistence = FakeJsonApiDemoPersistence()
    for index in range(10):
        persistence.save_project_record(_project_record(f"project_missing_{index}", None))

    store = ApiDemoStore(persistence=persistence)
    result = bootstrap_api_demo_store_from_persistence(store)

    assert result["azure_calls"] == 0
    assert result["loaded_projects"] == 10
    assert result["lazy_hydration_projects"] == 10
    assert len(store.lazy_hydration_project_ids) == 10


def test_existing_requirement_result_json_is_reused() -> None:
    persistence = FakeJsonApiDemoPersistence()
    persistence.save_project_record(_project_record("project_ready", _requirement_result("request_ready")))
    store = ApiDemoStore(persistence=persistence)
    bootstrap_api_demo_store_from_persistence(store)

    calls = {"hydration": 0}
    with _patched_demo_routers(store, calls):
        response = demo_routers.run_candidate_vendors(
            "project_ready",
            CandidateVendorsRequest(top_n=1, similarity_threshold=0.0),
        )

    assert response["ok"] is True
    assert calls["hydration"] == 0
    assert "project_ready" not in store.lazy_hydration_project_ids


class _patched_demo_routers:
    def __init__(self, store: ApiDemoStore, calls: dict[str, int]) -> None:
        self.store = store
        self.calls = calls
        self.original_store = demo_routers.store
        self.original_requirement_factory = demo_routers.create_requirement_ingestion_pipeline
        self.original_partner_factory = demo_routers.create_partner_matching_pipeline

    def __enter__(self):
        demo_routers.store = self.store
        demo_routers.create_requirement_ingestion_pipeline = self._requirement_factory
        demo_routers.create_partner_matching_pipeline = self._partner_factory
        return self

    def __exit__(self, exc_type, exc, tb):
        demo_routers.store = self.original_store
        demo_routers.create_requirement_ingestion_pipeline = self.original_requirement_factory
        demo_routers.create_partner_matching_pipeline = self.original_partner_factory

    def _requirement_factory(self):
        self.calls["hydration"] += 1
        return _FakeRequirementPipeline()

    def _partner_factory(self):
        return _FakePartnerMatchingPipeline()


class _FakeRequirementPipeline:
    def process_requirement_info(self, requirement: RequirementInfo, *, request_id: str | None = None):
        return _requirement_result(request_id or "request_lazy", requirement=requirement)


class _FakePartnerMatchingPipeline:
    def run(self, requirement_result, *, top_n: int, similarity_threshold: float):
        candidate = PartnerMatchCandidate(
            partner_name="효성ITX",
            specialty_tags=["LED전광판"],
            semantic_similarity_score=90.0,
            cosine_similarity=0.9,
            is_premium=True,
            success_rate=0.2,
            response_speed="normal",
            financial_status="normal",
            is_excluded=False,
            business_rule_passed=True,
            business_stage="selected_top_n",
            filter_reasons=[],
            check_required=[],
            sort_key=[90.0],
            rank=1,
            company_location="서울",
            installation_count=12,
            final_score=90.0,
            score_breakdown={"semantic_score": 90.0},
        )
        return PartnerMatchingResult(
            request_id=requirement_result.request_id,
            customer_name=requirement_result.requirement.customer_name,
            top_n=top_n,
            candidates=[candidate],
            all_candidates=[candidate],
            filtered_candidates=[],
            metadata={"partner_count": 1},
        )


def _project_record(project_id: str, requirement_result) -> ProjectRecord:
    return ProjectRecord(
        project_id=project_id,
        request_id=(requirement_result.request_id if requirement_result else f"request_{project_id}"),
        company_name="일강이앤아이",
        location="충북 음성",
        deadline="2026년 3월",
        request_text="\n".join(
            [
                "프로젝트명: 충북 음성 회의실 디스플레이",
                "활용 용도: 회의실 디스플레이 설치",
                "카테고리: LED전광판",
            ]
        ),
        requirement_result=requirement_result,
        created_at=datetime.now().isoformat(),
        original_request_text="회의실 디스플레이 설치",
        requirement_source="frontend_project_payload" if requirement_result else None,
    )


def _requirement_result(
    request_id: str,
    *,
    requirement: RequirementInfo | None = None,
) -> RequirementIngestionResult:
    requirement = requirement or RequirementInfo(
        raw_text="회의실 디스플레이 설치",
        customer_name="일강이앤아이",
        project_name="충북 음성 회의실 디스플레이",
        request_summary="회의실 LED전광판 설치",
        products=[
            RequirementProduct(
                product_type="LED전광판",
                name="LED전광판",
                quantity=1,
                unit="식",
                raw_text="LED전광판 1식",
            )
        ],
        region="충북 음성",
        install_schedule_text="2026년 3월",
        required_keywords=["LED전광판", "디스플레이"],
        metadata={"source": "frontend_project_payload"},
    )
    return RequirementIngestionResult(
        request_id=request_id,
        source_type="frontend_project_payload",
        source_path=None,
        requirement=requirement,
        embedding_text="고객사: 일강이앤아이\n카테고리: LED전광판",
        embedding_vector=[0.1, 0.2, 0.3],
        embedding_dim=3,
        raw_text_preview="회의실 디스플레이 설치",
        parser_warnings=[],
        parser_raw_matches={},
        ingestion_warnings=[],
        metadata={"requirement_source": "frontend_project_payload"},
    )


if __name__ == "__main__":
    main()
