from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


NOTE_HEADER_PATTERN = re.compile(
    r"^\s*(?:\[\s*)?(?:remark|특기사항|비고(?:\s*부분)?|기타사항|유의사항|참고사항)(?:\s*\])?\s*[:：]?\s*$",
    re.IGNORECASE,
)
NUMBER_PREFIX_PATTERN = re.compile(r"^\s*(?:\(?\d{1,2}\)?[.)]|[-*•])\s*")
LABEL_VALUE_PATTERN = re.compile(
    r"^\s*(?P<label>"
    r"결제\s*조건|결재\s*조건|대금\s*(?:결제|결재)(?:\s*조건)?|payment(?:\s*terms)?|"
    r"납\s*기|납기|delivery|도입가능일|"
    r"무상\s*a/?s|무상유지보수|무상보수기간|제품무상보증기간|보증기간|warranty(?:\s*term)?|"
    r"견적유효기간|price\s*validity|validity|"
    r"설치일정|도착지|packing|견적담당자|기타사항"
    r")\s*[.:\-：]?\s*(?P<value>.*)$",
    re.IGNORECASE,
)

SUMMARY_PATTERN = re.compile(
    r"(?:합\s*계|소\s*계|공급\s*가(?:액)?|부가\s*(?:세|가치세)|v\.?a\.?t|"
    r"총\s*금액|전\s*체\s*합\s*계|grand\s*total|total\s*amount)",
    re.IGNORECASE,
)
HEADER_FOOTER_PATTERN = re.compile(
    r"(?:^|\s)(?:수\s*신|담\s*당\s*자|견\s*적\s*일\s*자|견\s*적\s*번\s*호|"
    r"전\s*화\s*번\s*호|주소|이메일|fax|tel|홈페이지|사업자번호|은행\s*계좌|"
    r"bank\s*account|bank\s*name|swift|account\s*no\.?|beneficiary|대표이사|"
    r"공급자|견적담당자|건\s*명|o/?s\s*no\.?|품\s*명|품\s*목|상세\s*내역|"
    r"수량|단가|금\s*액)(?:\s|[:：]|$)",
    re.IGNORECASE,
)
SPEC_PATTERN = re.compile(
    r"(?:해상도|밝기|pixel\s*pitch|cabinet\s*size|module\s*size|규격|재질|steel|"
    r"분체도장|브라켓\s*설명|모델명|fhd|nit|bezel|video\s*wall\s*구성|"
    r"화면사이즈|최대소비전력)",
    re.IGNORECASE,
)
CONTRACT_RISK_PATTERN = re.compile(
    r"(?:전기|통신|인입공사|구조물|보강대|인테리어|마감|현장\s*실사|구조검토|"
    r"기구물|매립설치|돌출설치|cms|컨트롤러|콘텐츠|외부\s*유출|영업기회|"
    r"비용.*변경|불가할\s*수|제외|별도|필수|반드시)",
    re.IGNORECASE,
)
PAYMENT_CONTEXT_PATTERN = re.compile(
    r"(?:결제|결재|대금|payment|선입금|현금\s*결제|발주\s*시\s*\d+\s*%|"
    r"발주시\s*\d+\s*%)",
    re.IGNORECASE,
)
DELIVERY_CONTEXT_PATTERN = re.compile(
    r"(?:납\s*기|납기|delivery|도입가능일|발주\s*후|계약\s*후|납품.*이내)",
    re.IGNORECASE,
)
WARRANTY_CONTEXT_PATTERN = re.compile(
    r"(?:무상|보증|warranty|a/?s|유지보수|무상보수|factory\s*warranty)",
    re.IGNORECASE,
)
VALIDITY_CONTEXT_PATTERN = re.compile(
    r"(?:유효기간|validity|견적일로부터|발행\s*후)", re.IGNORECASE
)
INSTALL_SCHEDULE_PATTERN = re.compile(r"(?:설치일정|발주확정\s*후)", re.IGNORECASE)
MONEY_DOMINANT_PATTERN = re.compile(r"(?:₩|￦|\\)\s*[\d,]+")


@dataclass
class RuleNoteExtractionResult:
    payment_terms: str | None = None
    quote_validity_terms: str | None = None
    delivery_terms: list[str] = field(default_factory=list)
    warranty_terms: list[str] = field(default_factory=list)
    install_terms: list[str] = field(default_factory=list)
    special_notes: list[str] = field(default_factory=list)
    excluded_notes: list[dict[str, str]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


def extract_rule_notes(text: str) -> RuleNoteExtractionResult:
    result = RuleNoteExtractionResult()
    candidates = _collect_candidates(text)
    result.evidence["candidate_count"] = len(candidates)
    result.evidence["sections"] = sorted(
        {candidate["section"] for candidate in candidates if candidate["section"]}
    )

    payment_candidates: list[tuple[int, str, str]] = []
    pending_label = ""
    for candidate in candidates:
        line = candidate["text"]
        label, value = _split_label_value(line)
        if not label and pending_label:
            label, value = pending_label, line
            pending_label = ""
        content = value or line
        if label and not value:
            pending_label = label
            continue

        excluded_reason = _excluded_reason(line)
        if excluded_reason:
            result.excluded_notes.append({"text": line, "reason": excluded_reason})
            continue

        if _is_payment_candidate(label, line):
            cleaned = _clean_term_value(content)
            if is_valid_payment_terms(cleaned):
                payment_candidates.append(
                    (_payment_strength(label, cleaned), cleaned, line)
                )
            else:
                result.excluded_notes.append(
                    {"text": line, "reason": "invalid_payment_terms"}
                )
            continue

        if _is_delivery_candidate(label, line):
            _append_unique(result.delivery_terms, _clean_term_value(content))
            continue

        if _is_warranty_candidate(label, line):
            term = _clean_term_value(content)
            _append_unique(result.warranty_terms, term)
            if candidate["section"] and _is_actionable_special(line):
                _append_unique(result.special_notes, line)
            continue

        if _is_validity_candidate(label, line):
            result.quote_validity_terms = (
                result.quote_validity_terms or _clean_term_value(content)
            )
            continue

        if re.search(r"도착지", label, re.IGNORECASE):
            location = re.sub(r"\s*\([^)]*\)\s*$", "", _clean_term_value(content))
            if _looks_like_location(location):
                result.evidence["install_location"] = location
            continue

        if _is_install_term(label, line):
            _append_unique(result.install_terms, _clean_term_value(content))
            if _is_actionable_special(line):
                _append_unique(result.special_notes, line)
            continue

        if _is_special_candidate(candidate, line):
            _append_unique(result.special_notes, line)

    if payment_candidates:
        payment_candidates.sort(key=lambda item: item[0], reverse=True)
        result.payment_terms = payment_candidates[0][1]
        result.evidence["payment_terms_source"] = payment_candidates[0][2]

    result.special_notes = clean_special_notes(
        result.special_notes, payment_terms=result.payment_terms
    )
    result.evidence["special_note_sources"] = [
        {"text": item, "source": "note_section_or_actionable_condition"}
        for item in result.special_notes
    ]
    return result


def clean_special_notes(
    values: list[str] | str,
    *,
    payment_terms: str | None = None,
) -> list[str]:
    source_values = values if isinstance(values, list) else str(values).splitlines()
    notes: list[str] = []
    payment_compact = _compact(payment_terms or "")
    for value in source_values:
        line = _clean_candidate(value)
        if not line or NOTE_HEADER_PATTERN.match(line):
            continue
        if line.count("|") >= 2:
            continue
        if _excluded_reason(line):
            continue
        if payment_compact and _compact(_clean_term_value(line)) == payment_compact:
            continue
        if _is_payment_candidate("", line):
            continue
        if len(_compact(line)) < 4:
            continue
        _append_unique(notes, line)
    return notes


def is_valid_payment_terms(value: str | None) -> bool:
    if not value:
        return False
    compact = _compact(value)
    invalid = {
        "결제조건",
        "결재조건",
        "대금결제",
        "대금결재",
        "payment",
        "paymentterms",
        "ㅣ금결재",
        "금결재",
    }
    if compact.lower() in invalid or len(compact) < 2:
        return False
    if re.fullmatch(r"[ㅣ|▣\s:：\-]*대?금?결[제재]?[ㅣ|▣\s:：\-]*", value):
        return False
    return bool(
        re.search(r"(?:협의|선입금|현금|발주|설치|계약|\d+\s*%)", value, re.IGNORECASE)
    )


def extract_warranty_months(terms: list[str]) -> int | None:
    for term in terms:
        year = re.search(r"(\d+(?:\.\d+)?)\s*(?:년|year)", term, re.IGNORECASE)
        if year:
            return int(float(year.group(1)) * 12)
        month = re.search(r"(\d+(?:\.\d+)?)\s*(?:개월|months?)", term, re.IGNORECASE)
        if month:
            return int(float(month.group(1)))
    return None


def build_special_note_check_required(notes: list[str]) -> list[str]:
    return [note for note in notes if _is_actionable_special(note)]


def _collect_candidates(text: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    section = ""
    for raw_line in (text or "").splitlines():
        raw_line = str(raw_line)
        table_like = raw_line.count("|") >= 2
        if table_like:
            section = ""
        for fragment in _split_inline_candidates(raw_line):
            line = _clean_candidate(fragment)
            if not line:
                continue
            if NOTE_HEADER_PATTERN.match(line):
                section = line
                continue
            if section and _looks_like_section_boundary(line):
                section = ""
            candidates.append(
                {"text": line, "section": section, "table_like": table_like}
            )
    candidates.extend(_parallel_label_value_candidates(text))
    return candidates


def _parallel_label_value_candidates(text: str) -> list[dict[str, str]]:
    lines = [_clean_candidate(line) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    candidates: list[dict[str, str]] = []
    index = 0
    while index < len(lines):
        labels: list[str] = []
        cursor = index
        while cursor < len(lines):
            label, value = _split_label_value(lines[cursor])
            if not label or value:
                break
            labels.append(label)
            cursor += 1
        if len(labels) < 2 or cursor + len(labels) > len(lines):
            index += 1
            continue
        values = lines[cursor : cursor + len(labels)]
        if any(_split_label_value(value)[0] for value in values):
            index += 1
            continue
        candidates.extend(
            {"text": f"{label}: {value}", "section": "", "table_like": True}
            for label, value in zip(labels, values)
        )
        index = cursor + len(labels)
    return candidates


def _split_inline_candidates(raw_line: str) -> list[str]:
    line = re.sub(r"\s+", " ", raw_line).strip()
    if not line:
        return []
    numbered = re.split(
        r"\s+(?=(?:\(?\d{1,2}\)?[.)])\s+|[□▣]?\s*(?:payment|packing|validity)\b)",
        line,
        flags=re.IGNORECASE,
    )
    fragments: list[str] = []
    for value in numbered:
        if value.count("|") >= 2:
            fragments.extend(part.strip() for part in value.split("|") if part.strip())
        else:
            fragments.append(value)
    return fragments


def _looks_like_section_boundary(line: str) -> bool:
    compact = _compact(line)
    if NUMBER_PREFIX_PATTERN.match(line):
        return False
    return bool(
        re.fullmatch(
            r"(?:품명|품목|규격|수량|단가|금액|quotation|estimate|견적서)",
            compact,
            re.IGNORECASE,
        )
    )


def _clean_candidate(value: str) -> str:
    line = re.sub(r":?unselected:?", " ", str(value), flags=re.IGNORECASE)
    line = re.sub(r":?selected:?", " ", line, flags=re.IGNORECASE)
    line = re.sub(r"\s+", " ", line).strip(" \t|□▣")
    for pattern, replacement in [
        (r"견\s*적\s*유\s*효\s*기\s*간", "견적유효기간"),
        (r"무\s*상\s*보\s*수\s*기\s*간", "무상보수기간"),
        (r"유\s*상\s*보\s*수\s*정?\s*비\s*요\s*율", "유상보수정비요율"),
        (r"도\s*입\s*가\s*능\s*일", "도입가능일"),
        (r"도\s*착\s*지", "도착지"),
        (r"대\s*금\s*결\s*[제재]", "대금결재"),
        (r"결\s*제\s*조\s*건", "결제조건"),
        (r"납\s*기", "납기"),
    ]:
        line = re.sub(pattern, replacement, line, flags=re.IGNORECASE)
    line = NUMBER_PREFIX_PATTERN.sub("", line).strip()
    return line


def _split_label_value(line: str) -> tuple[str, str]:
    match = LABEL_VALUE_PATTERN.match(line)
    if not match:
        return "", ""
    return match.group("label").strip(), match.group("value").strip()


def _clean_term_value(value: str) -> str:
    value = _clean_candidate(value)
    match = LABEL_VALUE_PATTERN.match(value)
    if match and match.group("value").strip():
        value = match.group("value").strip()
    value = re.split(
        r"\s+(?=□?\s*(?:packing|validity|전\s*화\s*번\s*호|전화번호|fax|tel|"
        r"견적담당자|담당자))",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return value.strip(" .:：,-□▣")


def _excluded_reason(line: str) -> str | None:
    if SUMMARY_PATTERN.search(line):
        return "summary_amount"
    if HEADER_FOOTER_PATTERN.search(line):
        return "header_footer"
    if _money_dominant(line):
        return "money_dominant"
    if SPEC_PATTERN.search(line) and not CONTRACT_RISK_PATTERN.search(line):
        return "line_item_spec"
    return None


def _money_dominant(line: str) -> bool:
    money_pattern = re.compile(r"(?:₩|￦|\\)?\s*(?:\d{1,3},){1,4}\d{3}")
    if not MONEY_DOMINANT_PATTERN.search(line) and not money_pattern.search(line):
        return False
    remaining = money_pattern.sub("", MONEY_DOMINANT_PATTERN.sub("", line))
    remaining = re.sub(r"[\d,\s.+\-=/()]", "", remaining)
    return len(remaining) < 5


def _is_payment_candidate(label: str, line: str) -> bool:
    if re.search(r"payment|결제|결재|대금", label, re.IGNORECASE):
        return True
    return bool(PAYMENT_CONTEXT_PATTERN.search(line))


def _payment_strength(label: str, value: str) -> int:
    score = 2 if label else 0
    score += 2 if re.search(r"선입금|현금|발주\s*시|발주시", value) else 0
    score += 1 if re.search(r"\d+\s*%", value) else 0
    score += 1 if "협의" in value else 0
    return score


def _is_delivery_candidate(label: str, line: str) -> bool:
    return bool(
        re.search(r"납\s*기|delivery|도입가능일", label, re.IGNORECASE)
        or DELIVERY_CONTEXT_PATTERN.search(line)
    )


def _is_warranty_candidate(label: str, line: str) -> bool:
    return bool(
        re.search(r"무상|보증|warranty|a/?s|유지보수", label, re.IGNORECASE)
        or WARRANTY_CONTEXT_PATTERN.search(line)
    )


def _is_validity_candidate(label: str, line: str) -> bool:
    return bool(
        re.search(r"validity|유효기간", label, re.IGNORECASE)
        or VALIDITY_CONTEXT_PATTERN.search(line)
    )


def _is_install_term(label: str, line: str) -> bool:
    return bool(
        INSTALL_SCHEDULE_PATTERN.search(label)
        or (
            CONTRACT_RISK_PATTERN.search(line)
            and len(_compact(line)) >= 6
            and _compact(line) not in {"별도협의", "별도", "제외"}
        )
    )


def _is_actionable_special(line: str) -> bool:
    return bool(
        re.search(
            r"(?:(?:전기|통신|인입|인테리어|마감)\s*공사|제외|별도|필수|반드시|"
            r"현장\s*실사|현장답사|구조검토|"
            r"비용.*변경|불가할\s*수|외부\s*유출|영업기회|전원.*통신|"
            r"수요처\s*제공|사전에\s*확인)",
            line,
            re.IGNORECASE,
        )
    )


def _is_special_candidate(candidate: dict[str, str], line: str) -> bool:
    if candidate.get("table_like") and not _is_actionable_special(line):
        return False
    if not candidate["section"]:
        return bool(
            re.search(r"외부\s*유출|영업기회|관련\s*견적서|확인", line, re.IGNORECASE)
        )
    label, value = _split_label_value(line)
    if label and not value:
        return False
    if _is_actionable_special(line):
        return True
    return len(_compact(line)) >= 15 and bool(
        re.search(r"(?:견적서|관련\s*견적|드립니다|바랍니다|당부드립니다|있습니다|됩니다)[.)]?$", line)
    )


def _compact(value: str) -> str:
    return re.sub(r"[\s:：.\-_*▣|]", "", value or "")


def _looks_like_location(value: str) -> bool:
    return bool(
        value
        and re.search(
            r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|"
            r"전북|전남|경북|경남|제주|시|군|구|읍|면|동|로|길|현장|도착지)",
            value,
        )
    )


def _append_unique(values: list[str], value: str) -> None:
    value = value.strip()
    if value and value not in values:
        values.append(value)
