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


class ApiDemoStore:
    def __init__(self) -> None:
        self.projects: dict[str, ProjectRecord] = {}
        self.quote_pools: dict[str, QuotePoolRecord] = {}
        self.matches: dict[str, MatchRecord] = {}
        self.project_quote_pool_index: dict[str, str] = {}
        self.project_match_index: dict[str, list[str]] = {}

    def create_project(
        self,
        *,
        company_name: str,
        location: str | None,
        deadline: str | None,
        request_text: str,
        requirement_result,
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


store = ApiDemoStore()
