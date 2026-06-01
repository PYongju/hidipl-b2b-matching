import re
from pathlib import Path
from typing import Any


INVALID_VENDOR_NAMES = {
    "",
    "사업자",
    "사업자등록번호",
    "공급자",
    "법인명",
    "대표자",
    "상호",
    "상호명",
    "업체명",
    "회사명",
    "문서번호",
    "등록번호",
}

LABELS = {"법인명", "상호명", "회사명", "공급자명", "상호"}
SKIP_LABELS = {
    "사업자등록번호",
    "대표자",
    "주소",
    "사업장 주소",
    "사업장주소",
    "전화",
    "팩스",
    "업태",
    "종목",
}

PARTNER_ALIASES = {
    "hyosungitx": "효성ITX",
    "hyosung itx": "효성ITX",
    "효성itx": "효성ITX",
    "유어존": "유어존",
    "youzone": "유어존",
    "가이드삼정": "가이드삼정",
}


class VendorNameResolver:
    def __init__(self, partner_names: list[str] | None = None) -> None:
        self.partner_names = partner_names if partner_names is not None else self._load_partner_names()
        for alias_target in PARTNER_ALIASES.values():
            if alias_target not in self.partner_names:
                self.partner_names.append(alias_target)

    def resolve(
        self,
        current_vendor_name: str | None,
        source_text: str,
        source_file_path: str | None = None,
    ) -> tuple[str | None, dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        current = self._clean_candidate(current_vendor_name)

        if current and not is_invalid_vendor_name(current):
            candidates.append(
                {
                    "value": current,
                    "source": "original",
                    "confidence": 0.55,
                }
            )

        candidates.extend(self._find_label_next_line_candidates(source_text))
        candidates.extend(self._find_partner_master_candidates(source_text, source_file_path))
        candidates.extend(self._find_header_candidates(source_text))
        candidates.extend(self._find_file_name_candidates(source_file_path))

        valid_candidates = [
            candidate
            for candidate in candidates
            if self._is_valid_candidate(str(candidate.get("value") or ""))
        ]
        best = self._pick_best_candidate(valid_candidates)

        if not best:
            return None, {
                "vendor_name_source": "unresolved",
                "vendor_name_candidates": [candidate.get("value") for candidate in candidates],
                "normalized_vendor_name": "",
                "confidence": 0.0,
            }

        resolved = self._canonicalize_partner_name(str(best["value"]))
        debug_info = {
            "vendor_name_source": best.get("source"),
            "vendor_name_candidates": [candidate.get("value") for candidate in valid_candidates],
            "normalized_vendor_name": normalize_company_name(resolved),
            "confidence": best.get("confidence", 0.0),
        }
        return resolved, debug_info

    def _find_label_next_line_candidates(self, source_text: str) -> list[dict[str, Any]]:
        lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        candidates: list[dict[str, Any]] = []

        for index, line in enumerate(lines):
            label = line.strip(" :|-")
            if label not in LABELS:
                continue

            for offset in range(1, 4):
                if index + offset >= len(lines):
                    break

                candidate = self._clean_candidate(lines[index + offset])
                if not candidate:
                    continue
                if candidate.strip(" :|-") in SKIP_LABELS:
                    continue
                if self._is_valid_candidate(candidate):
                    candidates.append(
                        {
                            "value": candidate,
                            "source": "ocr_label_next_line",
                            "confidence": 0.9,
                        }
                    )
                    break

        return candidates

    def _find_partner_master_candidates(
        self,
        source_text: str,
        source_file_path: str | None,
    ) -> list[dict[str, Any]]:
        top_text = "\n".join(source_text.splitlines()[:50])
        normalized_text = normalize_company_name(top_text)
        normalized_file_name = normalize_company_name(Path(source_file_path).name if source_file_path else "")
        search_space = f"{normalized_text} {normalized_file_name}"
        candidates: list[dict[str, Any]] = []

        for alias, canonical in PARTNER_ALIASES.items():
            if normalize_company_name(alias) in search_space:
                candidates.append(
                    {
                        "value": canonical,
                        "source": "partner_alias",
                        "confidence": 0.98,
                    }
                )

        for partner_name in self.partner_names:
            normalized_partner = normalize_company_name(partner_name)
            if not normalized_partner:
                continue
            if normalized_partner in search_space:
                candidates.append(
                    {
                        "value": partner_name,
                        "source": "partner_master_text",
                        "confidence": 0.95,
                    }
                )

        return candidates

    def _find_header_candidates(self, source_text: str) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for line in source_text.splitlines()[:20]:
            candidate = self._clean_candidate(line)
            if not self._is_valid_candidate(candidate):
                continue
            if any(token in candidate for token in ["주식회사", "(주)", "㈜", "ITX", "itx"]):
                candidates.append(
                    {
                        "value": candidate,
                        "source": "header_company_candidate",
                        "confidence": 0.75,
                    }
                )
        return candidates

    def _find_file_name_candidates(
        self,
        source_file_path: str | None,
    ) -> list[dict[str, Any]]:
        if not source_file_path:
            return []

        file_name = Path(source_file_path).stem
        normalized_file_name = normalize_company_name(file_name)
        candidates: list[dict[str, Any]] = []

        for alias, canonical in PARTNER_ALIASES.items():
            if normalize_company_name(alias) in normalized_file_name:
                candidates.append(
                    {
                        "value": canonical,
                        "source": "file_name",
                        "confidence": 0.92,
                    }
                )

        for partner_name in self.partner_names:
            normalized_partner = normalize_company_name(partner_name)
            if normalized_partner and normalized_partner in normalized_file_name:
                candidates.append(
                    {
                        "value": partner_name,
                        "source": "file_name",
                        "confidence": 0.9,
                    }
                )

        return candidates

    def _pick_best_candidate(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not candidates:
            return None

        def sort_key(candidate: dict[str, Any]) -> tuple[float, int]:
            value = str(candidate.get("value") or "")
            return (
                float(candidate.get("confidence") or 0.0),
                len(normalize_company_name(value)),
            )

        return sorted(candidates, key=sort_key, reverse=True)[0]

    def _canonicalize_partner_name(self, value: str) -> str:
        normalized = normalize_company_name(value)
        for alias, canonical in PARTNER_ALIASES.items():
            if normalize_company_name(alias) == normalized:
                return canonical

        for partner_name in self.partner_names:
            if normalize_company_name(partner_name) == normalized:
                return partner_name

        value = re.sub(r"^\(?주\)?", "", value.strip(), flags=re.IGNORECASE)
        value = value.replace("㈜", "")
        value = value.replace("주식회사", "")
        return value.strip(" ()[]{}")

    def _is_valid_candidate(self, value: str | None) -> bool:
        value = self._clean_candidate(value)
        if not value:
            return False
        if is_invalid_vendor_name(value):
            return False
        if value.strip(" :|-") in SKIP_LABELS:
            return False
        if re.fullmatch(r"\d+", value):
            return False
        if re.search(r"\d{3}-\d{2}-\d{5}", value):
            return False
        if re.search(r"\d{2,4}-\d{3,4}-\d{4}", value):
            return False
        if len(normalize_company_name(value)) < 2:
            return False
        return True

    def _clean_candidate(self, value: str | None) -> str:
        if value is None:
            return ""

        cleaned = str(value).strip()
        cleaned = re.split(r"\s{2,}|\|", cleaned)[0]
        cleaned = cleaned.strip(" :|-")
        return cleaned

    def _load_partner_names(self) -> list[str]:
        try:
            from services.ranking.partner_loader import load_partner_profiles

            return [
                profile.name
                for profile in load_partner_profiles()
                if profile.name
            ]
        except Exception:
            return []


def is_invalid_vendor_name(value: str | None) -> bool:
    normalized = normalize_company_name(value or "")
    invalid_normalized = {
        normalize_company_name(invalid)
        for invalid in INVALID_VENDOR_NAMES
    }
    return normalized in invalid_normalized


def normalize_company_name(value: str) -> str:
    normalized = value.strip().lower()
    normalized = normalized.replace("㈜", "")
    normalized = re.sub(r"\(주\)|（주）|주식회사|주\)", "", normalized)
    normalized = re.sub(r"[\(\)\[\]\{\}]", "", normalized)
    normalized = re.sub(r"[^0-9a-z가-힣]", "", normalized)
    return normalized
