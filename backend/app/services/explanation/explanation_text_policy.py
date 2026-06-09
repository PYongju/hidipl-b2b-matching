from __future__ import annotations

import re
from typing import Iterable


PARSER_QUALITY_KEYWORDS = [
    "프로젝트명",
    "파일명 기준",
    "문서에서 명확히 추출",
    "parser",
    "Parser",
    "OCR",
    "item_name",
    "spec_raw",
    "파싱",
    "fallback",
    "보정됨",
    "파일명",
]


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def is_parser_quality_issue(message: str) -> bool:
    text = clean_text(message)
    return any(keyword in text for keyword in PARSER_QUALITY_KEYWORDS)


def is_decision_risk(message: str) -> bool:
    text = clean_text(message)
    if not text or is_parser_quality_issue(text):
        return False
    decision_keywords = [
        "납기",
        "별도협의",
        "가격 차이",
        "5% 초과",
        "공급가+VAT",
        "총액",
        "금액",
        "설치 범위",
        "설치 포함",
        "공사 별도",
        "보증",
        "확인 필요",
        "차이",
    ]
    return any(keyword in text for keyword in decision_keywords)


def is_comparison_risk(message: str) -> bool:
    text = clean_text(message)
    return any(
        keyword in text
        for keyword in [
            "가격 차이 5% 초과",
            "최저가 대비",
            "Top3 평균 대비",
            "다른 업체 대비",
            "사양 점수 낮음",
            "최종 점수 낮음",
        ]
    )


def split_check_required(messages: Iterable[str]) -> tuple[list[str], list[str]]:
    decision_risks: list[str] = []
    parser_notes: list[str] = []
    for message in messages or []:
        cleaned = clean_text(message)
        if not cleaned:
            continue
        if is_parser_quality_issue(cleaned):
            parser_notes.append(cleaned)
        elif is_comparison_risk(cleaned):
            continue
        elif is_decision_risk(cleaned):
            decision_risks.append(cleaned)
    return decision_risks, parser_notes


def split_comparison_risks(
    check_required: Iterable[str] = (),
    comparison_risks: Iterable[str] = (),
    rule_warnings: Iterable[str] = (),
) -> tuple[list[str], list[str]]:
    operational_checks: list[str] = []
    relative_risks: list[str] = []
    relative_keys: set[str] = set()

    def append_relative(value: str) -> None:
        key = normalize_risk_key(value)
        if key and key not in relative_keys:
            relative_keys.add(key)
            relative_risks.append(value)

    for message in check_required or []:
        cleaned = clean_text(message)
        if not cleaned:
            continue
        if is_comparison_risk(cleaned):
            append_relative(cleaned)
        elif cleaned not in operational_checks:
            operational_checks.append(cleaned)
    for message in [*(comparison_risks or []), *(rule_warnings or [])]:
        cleaned = clean_text(message)
        if is_comparison_risk(cleaned):
            append_relative(cleaned)
    return operational_checks, relative_risks


def compact_risk_text(text: str) -> str:
    cleaned = clean_text(text)
    rules = [
        (r"납기\s*정보가?\s*미기재.*", "납기 정보 미기재"),
        (r"납기\s*미기재.*", "납기 정보 미기재"),
        (r".*납기\s*별도협의.*", "납기 별도협의"),
        (r".*가격\s*차이\s*5%\s*초과.*", "가격 차이 5% 초과"),
        (r".*가격.*5%\s*이상.*", "가격 차이 5% 초과"),
        (r".*비용\s*검토.*", "가격 차이 5% 초과"),
        (r".*공급가\+VAT.*총액.*차이.*", "총액 차이 확인 필요"),
        (r".*견적서\s*총액.*차이.*", "총액 차이 확인 필요"),
        (r".*총액.*확인.*", "총액 차이 확인 필요"),
        (r".*설치.*범위.*확인.*", "설치 범위 확인 필요"),
        (r".*일부.*공사.*별도.*", "일부 공사 별도"),
        (r".*보증.*확인.*", "보증기간 확인 필요"),
    ]
    for pattern, replacement in rules:
        if re.search(pattern, cleaned):
            return replacement
    cleaned = cleaned.replace("되어 추가 확인 필요", "")
    cleaned = cleaned.replace("추가 확인 필요", "")
    return cleaned[:40]


def normalize_risk_key(text: str) -> str:
    normalized = compact_risk_text(text)
    normalized = normalized.replace("확인 필요", "")
    normalized = normalized.replace("추가", "")
    normalized = normalized.replace("되어", "")
    normalized = re.sub(r"[\s.,·/()]+", "", normalized)
    return normalized


def dedupe_short_texts(values: Iterable[str], *, limit: int = 2) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        cleaned = compact_risk_text(value)
        if not cleaned:
            continue
        key = normalize_risk_key(cleaned)
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def decision_weaknesses(
    *,
    llm_weaknesses: Iterable[str] = (),
    check_required: Iterable[str] = (),
    comparison_risks: Iterable[str] = (),
    filter_reasons: Iterable[str] = (),
    limit: int = 2,
) -> list[str]:
    candidates: list[str] = []
    for weakness in llm_weaknesses or []:
        cleaned = clean_text(weakness)
        if cleaned and not is_parser_quality_issue(cleaned):
            candidates.append(cleaned)
    decision_risks, _ = split_check_required(check_required)
    candidates.extend(decision_risks)
    candidates.extend(
        clean_text(risk) for risk in comparison_risks or [] if clean_text(risk)
    )
    candidates.extend(clean_text(reason) for reason in filter_reasons or [] if clean_text(reason))
    return dedupe_short_texts(candidates, limit=limit) or ["특이 리스크 없음"]


def has_risk(check_required: Iterable[str], keyword: str) -> bool:
    return any(keyword in clean_text(message) for message in check_required or [])


def trim_sentence(text: str, *, max_chars: int = 60) -> str:
    cleaned = clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"
