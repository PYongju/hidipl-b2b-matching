from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from services.api_demo.store_serialization import (
    deserialize_candidate_vendor_record,
    deserialize_match_record,
    deserialize_project_record,
    deserialize_quote_pool_record,
    serialize_candidate_vendor_record,
    serialize_match_record,
    serialize_project_record,
    serialize_quote_pool_record,
    sanitize_for_db_storage,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from services.api_demo.store import (
        CandidateVendorRecord,
        MatchRecord,
        ProjectRecord,
        QuotePoolRecord,
    )


class ApiDemoPersistence(ABC):
    @abstractmethod
    def save_project_record(self, record: ProjectRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_project_record(self, project_id: str) -> ProjectRecord | None:
        raise NotImplementedError

    @abstractmethod
    def save_quote_pool_record(self, record: QuotePoolRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_quote_pool_record(self, project_id: str) -> QuotePoolRecord | None:
        raise NotImplementedError

    @abstractmethod
    def save_match_record(self, record: MatchRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_match_record(self, project_id: str, match_id: str) -> MatchRecord | None:
        raise NotImplementedError

    @abstractmethod
    def load_latest_match_record(self, project_id: str) -> MatchRecord | None:
        raise NotImplementedError

    @abstractmethod
    def update_match_explanation(
        self,
        *,
        project_id: str,
        match_id: str,
        explanation_result: Any,
    ) -> None:
        raise NotImplementedError

    def update_project_requirement_result(
        self,
        *,
        project_id: str,
        requirement_result: Any,
    ) -> None:
        raise NotImplementedError

    def load_project_scalar_snapshot(self, project_id: str) -> dict[str, Any] | None:
        return None

    @abstractmethod
    def save_candidate_vendor_record(self, record: CandidateVendorRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_candidate_vendor_record(self, project_id: str) -> CandidateVendorRecord | None:
        raise NotImplementedError

    def load_recent_project_records(self, *, limit: int | None = None) -> list[ProjectRecord]:
        return []

    def load_recent_quote_pool_records(self, *, limit: int | None = None) -> list[QuotePoolRecord]:
        return []

    def load_recent_match_records(self, *, limit: int | None = None) -> list[MatchRecord]:
        return []

    def load_recent_candidate_vendor_records(
        self,
        *,
        limit: int | None = None,
    ) -> list[CandidateVendorRecord]:
        return []


class FakeJsonApiDemoPersistence(ApiDemoPersistence):
    def __init__(self) -> None:
        self.projects: dict[str, dict] = {}
        self.quote_pools: dict[str, dict] = {}
        self.project_quote_pool_index: dict[str, str] = {}
        self.matches: dict[str, dict] = {}
        self.project_match_index: dict[str, list[str]] = {}
        self.candidate_vendors: dict[str, dict] = {}
        self.project_candidate_vendor_index: dict[str, str] = {}

    def save_project_record(self, record: ProjectRecord) -> None:
        self.projects[record.project_id] = deepcopy(serialize_project_record(record))

    def load_project_record(self, project_id: str) -> ProjectRecord | None:
        data = self.projects.get(project_id)
        return deserialize_project_record(deepcopy(data)) if data else None

    def save_quote_pool_record(self, record: QuotePoolRecord) -> None:
        self.quote_pools[record.quote_pool_id] = deepcopy(serialize_quote_pool_record(record))
        self.project_quote_pool_index[record.project_id] = record.quote_pool_id

    def load_quote_pool_record(self, project_id: str) -> QuotePoolRecord | None:
        quote_pool_id = self.project_quote_pool_index.get(project_id)
        data = self.quote_pools.get(quote_pool_id or "")
        return deserialize_quote_pool_record(deepcopy(data)) if data else None

    def save_match_record(self, record: MatchRecord) -> None:
        self.matches[record.match_id] = deepcopy(serialize_match_record(record))
        match_ids = self.project_match_index.setdefault(record.project_id, [])
        if record.match_id not in match_ids:
            match_ids.append(record.match_id)

    def load_match_record(self, project_id: str, match_id: str) -> MatchRecord | None:
        data = self.matches.get(match_id)
        if not data or data.get("project_id") != project_id:
            return None
        return deserialize_match_record(deepcopy(data))

    def load_latest_match_record(self, project_id: str) -> MatchRecord | None:
        match_ids = self.project_match_index.get(project_id) or []
        if not match_ids:
            return None
        return self.load_match_record(project_id, match_ids[-1])

    def update_match_explanation(
        self,
        *,
        project_id: str,
        match_id: str,
        explanation_result: Any,
    ) -> None:
        data = self.matches.get(match_id)
        if not data or data.get("project_id") != project_id:
            return
        data["explanation_result"] = deepcopy(sanitize_for_db_storage(explanation_result))

    def update_project_requirement_result(
        self,
        *,
        project_id: str,
        requirement_result: Any,
    ) -> None:
        data = self.projects.get(project_id)
        if not data:
            return
        data["requirement_result"] = deepcopy(sanitize_for_db_storage(requirement_result))
        data["request_id"] = data["requirement_result"].get("request_id") or data.get("request_id")
        data["requirement_source"] = (
            (data["requirement_result"].get("metadata") or {}).get("requirement_source")
            or data.get("requirement_source")
        )

    def load_project_scalar_snapshot(self, project_id: str) -> dict[str, Any] | None:
        data = self.projects.get(project_id)
        if not data:
            return None
        return {
            "project_id": data.get("project_id"),
            "company_name": data.get("company_name"),
            "location": data.get("location"),
            "deadline": data.get("deadline"),
            "request_text": data.get("request_text"),
            "internal_notes": data.get("internal_notes"),
            "requirement_result": deepcopy(data.get("requirement_result")),
        }

    def save_candidate_vendor_record(self, record: CandidateVendorRecord) -> None:
        self.candidate_vendors[record.candidate_vendor_id] = deepcopy(
            serialize_candidate_vendor_record(record)
        )
        self.project_candidate_vendor_index[record.project_id] = record.candidate_vendor_id

    def load_candidate_vendor_record(self, project_id: str) -> CandidateVendorRecord | None:
        candidate_vendor_id = self.project_candidate_vendor_index.get(project_id)
        data = self.candidate_vendors.get(candidate_vendor_id or "")
        return deserialize_candidate_vendor_record(deepcopy(data)) if data else None

    def load_recent_project_records(self, *, limit: int | None = None) -> list[ProjectRecord]:
        values = list(self.projects.values())
        if limit is not None:
            values = values[-limit:]
        return [deserialize_project_record(deepcopy(data)) for data in values]

    def load_recent_quote_pool_records(self, *, limit: int | None = None) -> list[QuotePoolRecord]:
        values = list(self.quote_pools.values())
        if limit is not None:
            values = values[-limit:]
        return [deserialize_quote_pool_record(deepcopy(data)) for data in values]

    def load_recent_match_records(self, *, limit: int | None = None) -> list[MatchRecord]:
        values = list(self.matches.values())
        if limit is not None:
            values = values[-limit:]
        return [deserialize_match_record(deepcopy(data)) for data in values]

    def load_recent_candidate_vendor_records(
        self,
        *,
        limit: int | None = None,
    ) -> list[CandidateVendorRecord]:
        values = list(self.candidate_vendors.values())
        if limit is not None:
            values = values[-limit:]
        return [deserialize_candidate_vendor_record(deepcopy(data)) for data in values]


class SqlJsonApiDemoPersistence(ApiDemoPersistence):
    def __init__(self, session_factory=None, *, enabled: bool = True) -> None:
        if session_factory is None:
            from core.database import SessionLocal

            session_factory = SessionLocal
        self.session_factory = session_factory
        self.enabled = enabled

    def save_project_record(self, record: ProjectRecord) -> None:
        if not self.enabled:
            return
        data = serialize_project_record(record)
        self._execute_write(
            """
            INSERT INTO projects (
                project_id,
                status,
                company_name,
                location,
                deadline,
                request_text,
                requirement_result_json,
                created_at
            ) VALUES (
                :project_id,
                :status,
                :company_name,
                :location,
                :deadline,
                :request_text,
                :requirement_result_json,
                :created_at
            )
            ON DUPLICATE KEY UPDATE
                company_name = VALUES(company_name),
                location = VALUES(location),
                deadline = VALUES(deadline),
                request_text = VALUES(request_text),
                requirement_result_json = VALUES(requirement_result_json)
            """,
            {
                "project_id": record.project_id,
                "status": "created",
                "company_name": record.company_name,
                "location": record.location,
                "deadline": record.deadline,
                "request_text": record.request_text,
                "requirement_result_json": _json_dumps_or_none(
                    data.get("requirement_result")
                ),
                "created_at": _to_db_datetime(record.created_at),
            },
            "save_project_record",
        )

    def load_project_record(self, project_id: str) -> ProjectRecord | None:
        if not self.enabled:
            return None
        row = self._fetch_one(
            """
            SELECT
                project_id,
                company_name,
                location,
                deadline,
                request_text,
                requirement_result_json,
                created_at
            FROM projects
            WHERE project_id = :project_id
            """,
            {"project_id": project_id},
            "load_project_record",
        )
        if row is None:
            return None
        return self._row_to_project_record(row)

    def load_project_scalar_snapshot(self, project_id: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        row = self._fetch_one(
            """
            SELECT
                project_id,
                company_name,
                location,
                deadline,
                request_text,
                internal_notes,
                requirement_result_json
            FROM projects
            WHERE project_id = :project_id
            """,
            {"project_id": project_id},
            "load_project_scalar_snapshot",
        )
        if row is None:
            row = self._fetch_one(
                """
                SELECT
                    project_id,
                    company_name,
                    location,
                    deadline,
                    request_text,
                    requirement_result_json
                FROM projects
                WHERE project_id = :project_id
                """,
                {"project_id": project_id},
                "load_project_scalar_snapshot_without_internal_notes",
            )
        if row is None:
            return None
        return {
            "project_id": row.project_id,
            "company_name": row.company_name,
            "location": row.location,
            "deadline": row.deadline,
            "request_text": row.request_text,
            "internal_notes": getattr(row, "internal_notes", None),
            "requirement_result": _json_loads(row.requirement_result_json),
        }

    def save_quote_pool_record(self, record: QuotePoolRecord) -> None:
        if not self.enabled:
            return
        data = serialize_quote_pool_record(record)
        self._execute_write(
            """
            INSERT INTO quote_pools (
                quote_pool_id,
                project_id,
                uploaded_files_json,
                quote_ingestion_results_json,
                failed_files_json,
                created_at
            ) VALUES (
                :quote_pool_id,
                :project_id,
                :uploaded_files_json,
                :quote_ingestion_results_json,
                :failed_files_json,
                :created_at
            )
            ON DUPLICATE KEY UPDATE
                uploaded_files_json = VALUES(uploaded_files_json),
                quote_ingestion_results_json = VALUES(quote_ingestion_results_json),
                failed_files_json = VALUES(failed_files_json)
            """,
            {
                "quote_pool_id": record.quote_pool_id,
                "project_id": record.project_id,
                "uploaded_files_json": _json_dumps(data.get("uploaded_files") or []),
                "quote_ingestion_results_json": _json_dumps(
                    data.get("quote_ingestion_results") or []
                ),
                "failed_files_json": _json_dumps(data.get("failed_files") or []),
                "created_at": _to_db_datetime(record.created_at),
            },
            "save_quote_pool_record",
        )

    def load_quote_pool_record(self, project_id: str) -> QuotePoolRecord | None:
        if not self.enabled:
            return None
        row = self._fetch_one(
            """
            SELECT
                quote_pool_id,
                project_id,
                uploaded_files_json,
                quote_ingestion_results_json,
                failed_files_json,
                created_at
            FROM quote_pools
            WHERE project_id = :project_id
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"project_id": project_id},
            "load_quote_pool_record",
        )
        if row is None:
            return None
        quote_results = _json_loads(row.quote_ingestion_results_json)
        if quote_results is None:
            return None
        return deserialize_quote_pool_record(
            {
                "quote_pool_id": row.quote_pool_id,
                "project_id": row.project_id,
                "uploaded_files": _json_loads(row.uploaded_files_json) or [],
                "quote_ingestion_results": quote_results,
                "failed_files": _json_loads(row.failed_files_json) or [],
                "created_at": _date_to_iso(row.created_at),
            }
        )

    def save_match_record(self, record: MatchRecord) -> None:
        if not self.enabled:
            return
        data = serialize_match_record(record)
        self._execute_write(
            """
            INSERT INTO match_results (
                match_id,
                project_id,
                recommendation_result_json,
                explanation_result_json,
                created_at
            ) VALUES (
                :match_id,
                :project_id,
                :recommendation_result_json,
                :explanation_result_json,
                :created_at
            )
            ON DUPLICATE KEY UPDATE
                recommendation_result_json = VALUES(recommendation_result_json),
                explanation_result_json = COALESCE(
                    VALUES(explanation_result_json),
                    explanation_result_json
                )
            """,
            {
                "match_id": record.match_id,
                "project_id": record.project_id,
                "recommendation_result_json": _json_dumps(data.get("recommendation_result")),
                "explanation_result_json": _json_dumps_or_none(data.get("explanation_result")),
                "created_at": _to_db_datetime(record.created_at),
            },
            "save_match_record",
        )

    def load_match_record(self, project_id: str, match_id: str) -> MatchRecord | None:
        if not self.enabled:
            return None
        row = self._fetch_one(
            """
            SELECT
                match_id,
                project_id,
                recommendation_result_json,
                explanation_result_json,
                created_at
            FROM match_results
            WHERE project_id = :project_id
              AND match_id = :match_id
            """,
            {"project_id": project_id, "match_id": match_id},
            "load_match_record",
        )
        return self._row_to_match_record(row)

    def load_latest_match_record(self, project_id: str) -> MatchRecord | None:
        if not self.enabled:
            return None
        row = self._fetch_one(
            """
            SELECT
                match_id,
                project_id,
                recommendation_result_json,
                explanation_result_json,
                created_at
            FROM match_results
            WHERE project_id = :project_id
              AND recommendation_result_json IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"project_id": project_id},
            "load_latest_match_record",
        )
        return self._row_to_match_record(row)

    def update_match_explanation(
        self,
        *,
        project_id: str,
        match_id: str,
        explanation_result: Any,
    ) -> None:
        if not self.enabled:
            return
        self._execute_write(
            """
            UPDATE match_results
            SET explanation_result_json = :explanation_result_json
            WHERE project_id = :project_id
              AND match_id = :match_id
            """,
            {
                "project_id": project_id,
                "match_id": match_id,
                "explanation_result_json": _json_dumps(sanitize_for_db_storage(explanation_result)),
            },
            "update_match_explanation",
        )

    def update_project_requirement_result(
        self,
        *,
        project_id: str,
        requirement_result: Any,
    ) -> None:
        if not self.enabled:
            return
        self._execute_write(
            """
            UPDATE projects
            SET requirement_result_json = :requirement_result_json
            WHERE project_id = :project_id
            """,
            {
                "project_id": project_id,
                "requirement_result_json": _json_dumps(
                    sanitize_for_db_storage(requirement_result)
                ),
            },
            "update_project_requirement_result",
        )

    def save_candidate_vendor_record(self, record: CandidateVendorRecord) -> None:
        if not self.enabled:
            return
        data = serialize_candidate_vendor_record(record)
        self._execute_write(
            """
            INSERT INTO candidate_vendors (
                candidate_vendor_id,
                project_id,
                requirement_result_json,
                candidate_vendor_result_json,
                selected_vendor_names_json,
                requested_vendor_names_json,
                top_n,
                similarity_threshold,
                executed_at,
                created_at
            ) VALUES (
                :candidate_vendor_id,
                :project_id,
                :requirement_result_json,
                :candidate_vendor_result_json,
                :selected_vendor_names_json,
                :requested_vendor_names_json,
                :top_n,
                :similarity_threshold,
                :executed_at,
                :created_at
            )
            ON DUPLICATE KEY UPDATE
                requirement_result_json = VALUES(requirement_result_json),
                candidate_vendor_result_json = VALUES(candidate_vendor_result_json),
                selected_vendor_names_json = VALUES(selected_vendor_names_json),
                requested_vendor_names_json = VALUES(requested_vendor_names_json),
                top_n = VALUES(top_n),
                similarity_threshold = VALUES(similarity_threshold),
                executed_at = VALUES(executed_at)
            """,
            {
                "candidate_vendor_id": record.candidate_vendor_id,
                "project_id": record.project_id,
                "requirement_result_json": _json_dumps(data.get("requirement_result")),
                "candidate_vendor_result_json": _json_dumps(
                    data.get("candidate_vendor_result")
                ),
                "selected_vendor_names_json": _json_dumps(record.selected_vendor_names),
                "requested_vendor_names_json": _json_dumps(record.requested_vendor_names),
                "top_n": record.top_n,
                "similarity_threshold": record.similarity_threshold,
                "executed_at": _to_db_datetime(record.executed_at),
                "created_at": _to_db_datetime(record.created_at),
            },
            "save_candidate_vendor_record",
        )

    def load_candidate_vendor_record(self, project_id: str) -> CandidateVendorRecord | None:
        if not self.enabled:
            return None
        row = self._fetch_one(
            """
            SELECT
                candidate_vendor_id,
                project_id,
                requirement_result_json,
                candidate_vendor_result_json,
                selected_vendor_names_json,
                requested_vendor_names_json,
                top_n,
                similarity_threshold,
                executed_at,
                created_at
            FROM candidate_vendors
            WHERE project_id = :project_id
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"project_id": project_id},
            "load_candidate_vendor_record",
        )
        if row is None:
            return None
        requirement_result = _json_loads(row.requirement_result_json)
        candidate_result = _json_loads(row.candidate_vendor_result_json)
        if requirement_result is None or candidate_result is None:
            return None
        selected = _json_loads(row.selected_vendor_names_json) or []
        requested = _json_loads(row.requested_vendor_names_json) or []
        return deserialize_candidate_vendor_record(
            {
                "candidate_vendor_id": row.candidate_vendor_id,
                "project_id": row.project_id,
                "requirement_result": requirement_result,
                "candidate_vendor_result": candidate_result,
                "selected_vendor_names": selected,
                "selected_vendor_count": len(selected),
                "requested_vendor_names": requested,
                "requested_vendor_count": len(requested),
                "top_n": row.top_n or 10,
                "similarity_threshold": float(row.similarity_threshold or 60.0),
                "executed_at": _date_to_iso(row.executed_at),
                "created_at": _date_to_iso(row.created_at),
            }
        )

    def is_schema_ready(self) -> bool:
        if not self.enabled:
            return False
        try:
            with self.session_factory() as session:
                rows = session.execute(
                    text(
                        """
                        SELECT table_name, column_name
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND (
                            (table_name = 'projects' AND column_name = 'requirement_result_json')
                            OR (table_name = 'quote_pools' AND column_name = 'quote_ingestion_results_json')
                            OR (table_name = 'match_results' AND column_name = 'recommendation_result_json')
                            OR (table_name = 'match_results' AND column_name = 'explanation_result_json')
                            OR (table_name = 'candidate_vendors' AND column_name = 'candidate_vendor_result_json')
                          )
                        """
                    )
                ).fetchall()
            found = {(row.table_name, row.column_name) for row in rows}
            required = {
                ("projects", "requirement_result_json"),
                ("quote_pools", "quote_ingestion_results_json"),
                ("match_results", "recommendation_result_json"),
                ("match_results", "explanation_result_json"),
                ("candidate_vendors", "candidate_vendor_result_json"),
            }
            return required.issubset(found)
        except Exception as exc:
            logger.warning("API demo MySQL persistence schema check failed: %s", exc)
            return False

    def load_recent_project_records(self, *, limit: int | None = None) -> list[ProjectRecord]:
        rows = self._fetch_all(
            f"""
            SELECT
                project_id,
                company_name,
                location,
                deadline,
                request_text,
                requirement_result_json,
                created_at
            FROM projects
            ORDER BY created_at DESC
            {_limit_clause(limit)}
            """,
            {},
            "load_recent_project_records",
        )
        return [
            record
            for record in (self._row_to_project_record(row) for row in rows)
            if record is not None
        ]

    def load_recent_quote_pool_records(self, *, limit: int | None = None) -> list[QuotePoolRecord]:
        rows = self._fetch_all(
            f"""
            SELECT
                quote_pool_id,
                project_id,
                uploaded_files_json,
                quote_ingestion_results_json,
                failed_files_json,
                created_at
            FROM quote_pools
            ORDER BY created_at DESC
            {_limit_clause(limit)}
            """,
            {},
            "load_recent_quote_pool_records",
        )
        records = []
        for row in rows:
            quote_results = _json_loads(row.quote_ingestion_results_json)
            if quote_results is None:
                continue
            records.append(
                deserialize_quote_pool_record(
                    {
                        "quote_pool_id": row.quote_pool_id,
                        "project_id": row.project_id,
                        "uploaded_files": _json_loads(row.uploaded_files_json) or [],
                        "quote_ingestion_results": quote_results,
                        "failed_files": _json_loads(row.failed_files_json) or [],
                        "created_at": _date_to_iso(row.created_at),
                    }
                )
            )
        return records

    def load_recent_match_records(self, *, limit: int | None = None) -> list[MatchRecord]:
        rows = self._fetch_all(
            f"""
            SELECT
                match_id,
                project_id,
                recommendation_result_json,
                explanation_result_json,
                created_at
            FROM match_results
            WHERE recommendation_result_json IS NOT NULL
            ORDER BY created_at DESC
            {_limit_clause(limit)}
            """,
            {},
            "load_recent_match_records",
        )
        return [
            record
            for record in (self._row_to_match_record(row) for row in rows)
            if record is not None
        ]

    def load_recent_candidate_vendor_records(
        self,
        *,
        limit: int | None = None,
    ) -> list[CandidateVendorRecord]:
        rows = self._fetch_all(
            f"""
            SELECT
                candidate_vendor_id,
                project_id,
                requirement_result_json,
                candidate_vendor_result_json,
                selected_vendor_names_json,
                requested_vendor_names_json,
                top_n,
                similarity_threshold,
                executed_at,
                created_at
            FROM candidate_vendors
            ORDER BY created_at DESC
            {_limit_clause(limit)}
            """,
            {},
            "load_recent_candidate_vendor_records",
        )
        records = []
        for row in rows:
            record = self._row_to_candidate_vendor_record(row)
            if record is not None:
                records.append(record)
        return records

    def _row_to_project_record(self, row) -> ProjectRecord | None:
        if row is None:
            return None
        requirement_result = _json_loads(row.requirement_result_json)
        request_id = (
            requirement_result.get("request_id")
            if isinstance(requirement_result, dict)
            else None
        )
        return deserialize_project_record(
            {
                "project_id": row.project_id,
                "request_id": request_id or f"request_{row.project_id}",
                "company_name": row.company_name,
                "location": row.location,
                "deadline": row.deadline,
                "request_text": row.request_text or "",
                "requirement_result": requirement_result,
                "created_at": _date_to_iso(row.created_at),
                "original_request_text": row.request_text,
                "requirement_source": (
                    (requirement_result.get("metadata") or {}).get("requirement_source")
                    if isinstance(requirement_result, dict)
                    else None
                ),
            }
        )

    def _row_to_candidate_vendor_record(self, row) -> CandidateVendorRecord | None:
        if row is None:
            return None
        requirement_result = _json_loads(row.requirement_result_json)
        candidate_result = _json_loads(row.candidate_vendor_result_json)
        if requirement_result is None or candidate_result is None:
            return None
        selected = _json_loads(row.selected_vendor_names_json) or []
        requested = _json_loads(row.requested_vendor_names_json) or []
        return deserialize_candidate_vendor_record(
            {
                "candidate_vendor_id": row.candidate_vendor_id,
                "project_id": row.project_id,
                "requirement_result": requirement_result,
                "candidate_vendor_result": candidate_result,
                "selected_vendor_names": selected,
                "selected_vendor_count": len(selected),
                "requested_vendor_names": requested,
                "requested_vendor_count": len(requested),
                "top_n": row.top_n or 10,
                "similarity_threshold": float(row.similarity_threshold or 60.0),
                "executed_at": _date_to_iso(row.executed_at),
                "created_at": _date_to_iso(row.created_at),
            }
        )

    def _row_to_match_record(self, row) -> MatchRecord | None:
        if row is None:
            return None
        recommendation = _json_loads(row.recommendation_result_json)
        if recommendation is None:
            return None
        return deserialize_match_record(
            {
                "match_id": row.match_id,
                "project_id": row.project_id,
                "recommendation_result": recommendation,
                "explanation_result": _json_loads(row.explanation_result_json),
                "created_at": _date_to_iso(row.created_at),
            }
        )

    def _execute_write(self, sql: str, params: dict[str, Any], operation: str) -> None:
        try:
            with self.session_factory() as session:
                session.execute(text(sql), params)
                session.commit()
        except Exception as exc:
            logger.warning("API demo MySQL persistence %s failed: %s", operation, exc)

    def _fetch_one(self, sql: str, params: dict[str, Any], operation: str):
        try:
            with self.session_factory() as session:
                return session.execute(text(sql), params).fetchone()
        except Exception as exc:
            logger.warning("API demo MySQL persistence %s failed: %s", operation, exc)
            return None

    def _fetch_all(self, sql: str, params: dict[str, Any], operation: str):
        try:
            with self.session_factory() as session:
                return session.execute(text(sql), params).fetchall()
        except Exception as exc:
            logger.warning("API demo MySQL persistence %s failed: %s", operation, exc)
            return []


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_dumps_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return _json_dumps(value)


def _json_loads(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return json.loads(value)


def _date_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _to_db_datetime(value: Any) -> Any:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _limit_clause(limit: int | None) -> str:
    if limit is None:
        return ""
    try:
        normalized = int(limit)
    except (TypeError, ValueError):
        return ""
    if normalized <= 0:
        return ""
    return f"LIMIT {normalized}"
