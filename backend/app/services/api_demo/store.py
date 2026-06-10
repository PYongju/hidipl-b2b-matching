from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class ProjectRecord:
    project_id: str
    request_id: str
    company_name: str
    location: str | None
    deadline: str | None
    request_text: str
    requirement_result: Any
    created_at: str
    original_request_text: str | None = None
    requirement_source: str | None = None


@dataclass
class QuotePoolRecord:
    quote_pool_id: str
    project_id: str
    uploaded_files: list[str]
    quote_ingestion_results: list[Any]
    failed_files: list[dict[str, str]]
    created_at: str


@dataclass
class MatchRecord:
    match_id: str
    project_id: str
    recommendation_result: Any
    explanation_result: Any | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CandidateVendorRecord:
    candidate_vendor_id: str
    project_id: str
    requirement_result: Any
    candidate_vendor_result: Any
    selected_vendor_names: list[str]
    selected_vendor_count: int
    requested_vendor_names: list[str]
    requested_vendor_count: int
    top_n: int
    similarity_threshold: float
    executed_at: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ApiDemoStore:
    def __init__(self) -> None:
        self.projects: dict[str, ProjectRecord] = {}
        self.quote_pools: dict[str, QuotePoolRecord] = {}
        self.matches: dict[str, MatchRecord] = {}
        self.candidate_vendors: dict[str, CandidateVendorRecord] = {}
        self.project_quote_pool_index: dict[str, str] = {}
        self.project_match_index: dict[str, list[str]] = {}
        self.project_candidate_vendor_index: dict[str, str] = {}

    def create_project(
        self,
        *,
        company_name: str,
        location: str | None,
        deadline: str | None,
        request_text: str,
        requirement_result,
        original_request_text: str | None = None,
        requirement_source: str | None = None,
    ) -> ProjectRecord:
        project_id = f"project_{uuid4().hex[:8]}"
        request_id = requirement_result.request_id or f"request_{uuid4().hex[:8]}"
        record = ProjectRecord(
            project_id=project_id,
            request_id=request_id,
            company_name=company_name,
            location=location,
            deadline=deadline,
            request_text=request_text,
            requirement_result=requirement_result,
            created_at=datetime.now().isoformat(),
            original_request_text=original_request_text,
            requirement_source=requirement_source,
        )
        self.projects[project_id] = record
        return record

    def save_quote_pool(
        self,
        *,
        project_id: str,
        uploaded_files: list[str],
        quote_ingestion_results: list[Any],
        failed_files: list[dict[str, str]],
    ) -> QuotePoolRecord:
        quote_pool_id = f"quote_pool_{uuid4().hex[:8]}"
        record = QuotePoolRecord(
            quote_pool_id=quote_pool_id,
            project_id=project_id,
            uploaded_files=uploaded_files,
            quote_ingestion_results=quote_ingestion_results,
            failed_files=failed_files,
            created_at=datetime.now().isoformat(),
        )
        self.quote_pools[quote_pool_id] = record
        self.project_quote_pool_index[project_id] = quote_pool_id
        return record

    def save_match(
        self,
        *,
        project_id: str,
        recommendation_result,
        explanation_result=None,
    ) -> MatchRecord:
        match_id = f"match_{uuid4().hex[:8]}"
        record = MatchRecord(
            match_id=match_id,
            project_id=project_id,
            recommendation_result=recommendation_result,
            explanation_result=explanation_result,
        )
        self.matches[match_id] = record
        self.project_match_index.setdefault(project_id, []).append(match_id)
        return record

    def save_candidate_vendors(
        self,
        *,
        project_id: str,
        requirement_result,
        candidate_vendor_result,
        top_n: int,
        similarity_threshold: float,
        requested_vendor_names: list[str] | None = None,
    ) -> CandidateVendorRecord:
        candidate_vendor_id = f"candidate_vendors_{uuid4().hex[:8]}"
        selected_vendor_names = [
            candidate.partner_name
            for candidate in candidate_vendor_result.candidates
            if getattr(candidate, "partner_name", None)
        ]
        requested_names = list(requested_vendor_names or selected_vendor_names)
        record = CandidateVendorRecord(
            candidate_vendor_id=candidate_vendor_id,
            project_id=project_id,
            requirement_result=requirement_result,
            candidate_vendor_result=candidate_vendor_result,
            selected_vendor_names=selected_vendor_names,
            selected_vendor_count=len(selected_vendor_names),
            requested_vendor_names=requested_names,
            requested_vendor_count=len(requested_names),
            top_n=top_n,
            similarity_threshold=similarity_threshold,
            executed_at=datetime.now().isoformat(),
        )
        self.candidate_vendors[candidate_vendor_id] = record
        self.project_candidate_vendor_index[project_id] = candidate_vendor_id
        return record

    def get_project(self, project_id: str) -> ProjectRecord | None:
        return self.projects.get(project_id)

    def get_quote_pool(self, project_id: str) -> QuotePoolRecord | None:
        quote_pool_id = self.project_quote_pool_index.get(project_id)
        return self.quote_pools.get(quote_pool_id or "")

    def get_latest_match(self, project_id: str) -> MatchRecord | None:
        match_ids = self.project_match_index.get(project_id) or []
        if not match_ids:
            return None
        return self.matches.get(match_ids[-1])

    def get_match(self, project_id: str, match_id: str) -> MatchRecord | None:
        match = self.matches.get(match_id)
        if match is None or match.project_id != project_id:
            return None
        return match

    def get_candidate_vendors(self, project_id: str) -> CandidateVendorRecord | None:
        candidate_vendor_id = self.project_candidate_vendor_index.get(project_id)
        return self.candidate_vendors.get(candidate_vendor_id or "")


store = ApiDemoStore()
