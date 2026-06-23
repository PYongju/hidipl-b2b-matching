from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from services.parser.quote_parser_validator import build_amount_validation, normalize_line_item_category
from services.parser.schemas import LineItem, LineItemCategory
from services.quote_ingestion.schemas import QuoteIngestionResult


MULTI_OPTION_CHECK_MESSAGE = "문서 내 복수 옵션 견적 확인 필요"
MULTI_OPTION_SPLIT_FAILED_MESSAGE = "복수 옵션 자동 분리 실패, 수동 확인 필요"
MULTI_OPTION_SPLIT_METHOD = "sequential_line_item_sum"


def split_multi_option_result(
    result: QuoteIngestionResult,
    *,
    tolerance: int = 10_000,
) -> list[QuoteIngestionResult]:
    raw_matches = result.parser_raw_matches or {}
    detection = raw_matches.get("multi_option_detection") or {}
    candidates = detection.get("option_total_candidates") or []
    if not detection.get("is_multi_option_possible") or len(candidates) < 2:
        return [result]

    line_item_corrections = normalize_split_line_item_amounts(result.quote)
    if line_item_corrections:
        raw_matches["line_item_corrections"] = line_item_corrections
    groups = split_line_items_by_option_totals(
        result.quote.line_items,
        candidates,
        tolerance=tolerance,
    )
    split_method = MULTI_OPTION_SPLIT_METHOD
    split_confidence = "high"
    if not groups:
        groups = split_line_items_by_product_group_boundary(
            result.quote.line_items,
            detection.get("product_groups") or [],
            expected_group_count=len(candidates),
        )
        split_method = "product_group_boundary"
        split_confidence = "medium"
        if groups and not _groups_match_candidates(groups, candidates, tolerance=tolerance):
            reconciled = _reconcile_product_groups_to_candidates(
                groups,
                candidates,
                tolerance=tolerance,
                source_text=result.ocr_text_preview or "",
            )
            if reconciled:
                groups = reconciled
                split_method = (
                    "product_group_boundary_with_unparsed_residual"
                    if _groups_have_residual(groups)
                    else "product_group_boundary_section_reconstructed"
                )
                split_confidence = "medium"
            else:
                groups = None
        if not groups:
            _mark_split_failed(
                result,
                reason="line_items cumulative sum did not match option total candidates",
            )
            return [result]

    labels = _resolve_option_labels(
        candidates,
        detection.get("product_groups") or [],
        groups,
    )
    split_results = []
    parent_quote_id = result.quote_id or result.quote.quote_id
    for index, (candidate, label, line_items) in enumerate(
        zip(candidates, labels, groups),
        start=1,
    ):
        split_results.append(
            _build_split_result(
                result,
                candidate=candidate,
                label=label,
                line_items=line_items,
                option_index=index,
                parent_quote_id=parent_quote_id,
                split_method=split_method,
                split_confidence=split_confidence,
            )
        )

    return split_results


def split_line_items_by_option_totals(
    line_items,
    option_total_candidates: list[dict[str, Any]],
    *,
    tolerance: int = 10_000,
) -> list[list[Any]] | None:
    groups = []
    cursor = 0
    for candidate in option_total_candidates:
        target = _to_int(candidate.get("supply_price"))
        if target is None:
            return None
        group = []
        running_sum = 0
        while cursor < len(line_items):
            item = line_items[cursor]
            group.append(item)
            running_sum += _line_item_amount(item) or 0
            cursor += 1
            if abs(running_sum - target) <= tolerance:
                break
        if abs(running_sum - target) > tolerance:
            return None
        groups.append(group)

    if cursor < len(line_items):
        return None
    return groups


def split_line_items_by_product_group_boundary(
    line_items,
    product_groups: list[str],
    *,
    expected_group_count: int,
) -> list[list[Any]] | None:
    if expected_group_count != 2 or len(product_groups) < 2:
        return None
    boundary = None
    for index, item in enumerate(line_items):
        if index == 0:
            continue
        text = f"{getattr(item, 'name', '')} {getattr(item, 'spec_raw', '')}".lower()
        if "비디오월" in text or "video wall" in text:
            boundary = index
            break
    if boundary is None:
        return None
    first = list(line_items[:boundary])
    second = list(line_items[boundary:])
    if not first or not second:
        return None
    return [first, second]


def _build_split_result(
    parent: QuoteIngestionResult,
    *,
    candidate: dict[str, Any],
    label: str,
    line_items: list[Any],
    option_index: int,
    parent_quote_id: str | None,
    split_method: str,
    split_confidence: str,
) -> QuoteIngestionResult:
    quote = deepcopy(parent.quote)
    quote.line_items = deepcopy(line_items)
    quote.total_supply_price = int(candidate["supply_price"])
    quote.total_with_vat = int(candidate["total_with_vat"])
    quote.project_name = _append_option_label(quote.project_name, label)
    quote.quote_id = _build_option_quote_id(parent_quote_id or quote.quote_id, option_index, label)
    line_item_corrections = normalize_split_line_item_amounts(quote)

    raw_matches = deepcopy(parent.parser_raw_matches or {})
    amount_validation = build_amount_validation(
        quote,
        quoted_tax_amount=_to_int(candidate.get("tax_amount")),
    )
    raw_matches["quoted_tax_amount"] = _to_int(candidate.get("tax_amount"))
    raw_matches["amount_validation"] = amount_validation
    raw_matches["multi_option_split"] = {
        "split_from_multi_option": True,
        "parent_quote_id": parent_quote_id,
        "option_index": option_index,
            "option_label": label,
            "line_item_count": len(quote.line_items),
        "auto_split": True,
        "split_method": split_method,
        "split_confidence": split_confidence,
        }
    raw_matches["line_item_corrections"] = line_item_corrections
    raw_matches["multi_option_detection"] = {
        **(raw_matches.get("multi_option_detection") or {}),
        "auto_split": True,
    }
    amount_message = amount_validation.get("message")
    raw_matches["parser_check_required"] = _clean_parser_checks(
        raw_matches.get("parser_check_required") or [],
        amount_message=amount_message,
    )
    if any((getattr(item, "spec_parsed", {}) or {}).get("reconciliation_residual") for item in quote.line_items):
        raw_matches["parser_check_required"].append("일부 금액이 개별 품목으로 복원되지 않아 확인 필요")
        raw_matches["parser_check_required"] = list(dict.fromkeys(raw_matches["parser_check_required"]))

    metadata = deepcopy(parent.metadata or {})
    metadata["parser_check_required"] = _clean_parser_checks(
        metadata.get("parser_check_required") or raw_matches.get("parser_check_required") or [],
        amount_message=amount_message,
    )
    metadata.update(
        {
            "split_from_multi_option": True,
            "parent_quote_id": parent_quote_id,
            "option_index": option_index,
            "option_label": label,
            "option_total_candidate": {
                "supply_price": _to_int(candidate.get("supply_price")),
                "tax_amount": _to_int(candidate.get("tax_amount")),
                "total_with_vat": _to_int(candidate.get("total_with_vat")),
            },
            "split_method": split_method,
            "split_confidence": _verified_split_confidence(amount_validation, split_confidence),
        }
    )
    metadata["line_item_corrections"] = line_item_corrections
    metadata["parser_check_required"] = raw_matches["parser_check_required"]

    return QuoteIngestionResult(
        quote_id=quote.quote_id,
        request_id=parent.request_id,
        source_file_path=parent.source_file_path,
        quote=quote,
        embedding_text="",
        embedding_vector=None,
        embedding_dim=None,
        ocr_text_preview=parent.ocr_text_preview,
        parser_warnings=_clean_parser_warnings(
            parent.parser_warnings,
            amount_message=amount_message,
        ),
        parser_raw_matches=raw_matches,
        ingestion_warnings=list(parent.ingestion_warnings),
        metadata=metadata,
    )


def _mark_split_failed(result: QuoteIngestionResult, *, reason: str) -> None:
    raw_matches = result.parser_raw_matches or {}
    raw_matches["multi_option_split"] = {
        "split_from_multi_option": False,
        "auto_split": False,
        "split_failed_reason": reason,
    }
    checks = raw_matches.get("parser_check_required") or []
    if not isinstance(checks, list):
        checks = [str(checks)]
    checks.append(MULTI_OPTION_SPLIT_FAILED_MESSAGE)
    raw_matches["parser_check_required"] = list(dict.fromkeys(str(item) for item in checks if item))
    result.parser_raw_matches = raw_matches
    result.metadata["parser_check_required"] = raw_matches["parser_check_required"]
    result.metadata["split_failed_reason"] = reason


def normalize_split_line_item_amounts(quote) -> list[dict[str, Any]]:
    corrections = []
    for item in quote.line_items:
        before = _line_item_snapshot(item)
        reason = None
        text = f"{getattr(item, 'name', '')} {getattr(item, 'spec_raw', '')}".lower()

        if _is_led_display_item(text) and _looks_like_total_as_unit_price(item):
            cabinet_quantity = _extract_cabinet_quantity(text)
            amount = _line_item_amount(item)
            if cabinet_quantity and amount and amount % cabinet_quantity == 0:
                item.quantity = float(cabinet_quantity)
                item.unit_price = int(amount / cabinet_quantity)
                item.total_price = amount
                reason = f"LED cabinet quantity correction: quantity={cabinet_quantity}"

        if _is_single_player_item(text) and _looks_like_row_number_quantity(item):
            item.quantity = 1.0
            if getattr(item, "unit_price", None) is not None:
                item.total_price = int(item.unit_price)
            reason = "row number was likely used as quantity"

        after = _line_item_snapshot(item)
        if reason and before != after:
            corrections.append(
                {
                    "item_name": getattr(item, "name", ""),
                    "field": "quantity/unit_price/supply_amount",
                    "before": before,
                    "after": after,
                    "reason": reason,
                    "auto_corrected": True,
                }
            )
    return corrections


def _verified_split_confidence(amount_validation: dict[str, Any], default: str) -> str:
    if amount_validation.get("line_items_difference") in (None, 0):
        return "high"
    return default


def _line_item_snapshot(item) -> dict[str, Any]:
    return {
        "quantity": getattr(item, "quantity", None),
        "unit_price": getattr(item, "unit_price", None),
        "supply_amount": getattr(item, "total_price", None),
    }


def _is_led_display_item(text: str) -> bool:
    return "led display" in text or "led전광판" in text or "led 전광판" in text


def _looks_like_total_as_unit_price(item) -> bool:
    quantity = getattr(item, "quantity", None)
    unit_price = getattr(item, "unit_price", None)
    total_price = getattr(item, "total_price", None)
    return quantity in (1, 1.0, None) and unit_price is not None and total_price == unit_price


def _extract_cabinet_quantity(text: str) -> int | None:
    match = re.search(
        r"(?:함체\s*수량|cabinet\s*quantity)[^\d]*(\d{1,3})\s*(?:x|×|\*)\s*(\d{1,3})(?:\s*=\s*(\d{1,3}))?",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        left = int(match.group(1))
        right = int(match.group(2))
        explicit = int(match.group(3)) if match.group(3) else None
        return explicit or left * right
    match = re.search(r"(?:함체\s*수량|cabinet\s*quantity)[^\d]*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})", text)
    if match:
        return int(match.group(3))
    return None


def _is_single_player_item(text: str) -> bool:
    return any(
        keyword in text
        for keyword in [
            "vx400pro",
            "all-in-one",
            "all in one",
            "controller",
            "player",
            "플레이어",
            "컨트롤러",
        ]
    )


def _looks_like_row_number_quantity(item) -> bool:
    quantity = getattr(item, "quantity", None)
    unit_price = getattr(item, "unit_price", None)
    total_price = getattr(item, "total_price", None)
    if quantity not in (2, 2.0, 3, 3.0, 4, 4.0):
        return False
    if unit_price is None or total_price is None:
        return False
    expected = int(unit_price * quantity)
    return abs(total_price - expected) <= 10_000 or total_price != unit_price


def _resolve_option_labels(
    candidates: list[dict[str, Any]],
    product_groups: list[str],
    groups: list[list[Any]],
) -> list[str]:
    labels = []
    for index, candidate in enumerate(candidates):
        label = _clean_label(candidate.get("label"))
        if not label and index < len(product_groups):
            label = _clean_label(product_groups[index])
        if not label and index < len(groups):
            label = _infer_label_from_line_items(groups[index])
        labels.append(label or f"option_{index + 1}")
    return labels


def _infer_label_from_line_items(line_items: list[Any]) -> str | None:
    text = " ".join(
        f"{getattr(item, 'name', '')} {getattr(item, 'spec_raw', '')}"
        for item in line_items
    ).lower()
    if "led" in text or "전광판" in text:
        return "LED전광판"
    if "비디오월" in text or "video wall" in text:
        return "비디오월"
    for item in line_items:
        if getattr(item, "category", None) == LineItemCategory.DISPLAY:
            return _clean_label(getattr(item, "name", None))
    return None


def _clean_parser_checks(checks: list[Any], *, amount_message: str | None = None) -> list[str]:
    result = []
    for check in checks:
        text = str(check).strip()
        if not text:
            continue
        if text == MULTI_OPTION_CHECK_MESSAGE:
            continue
        if "복수 옵션" in text and "자동 분리 실패" not in text:
            continue
        if _is_amount_message(text):
            continue
        if text not in result:
            result.append(text)
    if amount_message and amount_message not in result:
        result.insert(0, amount_message)
    return result


def _clean_parser_warnings(warnings: list[Any], *, amount_message: str | None = None) -> list[str]:
    result = []
    for warning in warnings:
        text = str(warning).strip()
        if not text or _is_amount_message(text):
            continue
        if text not in result:
            result.append(text)
    if amount_message and amount_message not in result:
        result.append(amount_message)
    return result


def _is_amount_message(text: str) -> bool:
    return (
        "line_items 합계" in text
        or "공급가+VAT" in text
        or "VAT가 공급가" in text
    )


def _append_option_label(project_name: str, label: str) -> str:
    project_name = str(project_name or "").strip()
    label = _clean_label(label) or ""
    if not label:
        return project_name
    if label in project_name:
        return project_name
    return f"{project_name} - {label}" if project_name else label


def _build_option_quote_id(parent_quote_id: str, option_index: int, label: str) -> str:
    suffix = _safe_id_part(label) or f"option_{option_index}"
    return f"{parent_quote_id}_opt{option_index}_{suffix}"


def _safe_id_part(value: str) -> str:
    text = re.sub(r"\s+", "_", str(value or "").strip())
    text = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def _clean_label(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip(" -_:")
    return text or None


def _line_item_amount(item) -> int | None:
    if getattr(item, "total_price", None) is not None:
        return int(item.total_price)
    if getattr(item, "unit_price", None) is not None and getattr(item, "quantity", None) is not None:
        return int(item.unit_price * item.quantity)
    return None


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _groups_match_candidates(
    groups: list[list[Any]],
    candidates: list[dict[str, Any]],
    *,
    tolerance: int,
) -> bool:
    if len(groups) != len(candidates):
        return False
    for group, candidate in zip(groups, candidates):
        target = _to_int(candidate.get("supply_price"))
        if target is None:
            return False
        actual = sum(_line_item_amount(item) or 0 for item in group)
        if abs(actual - target) > tolerance:
            return False
    return True


def _reconcile_product_groups_to_candidates(
    groups: list[list[Any]],
    candidates: list[dict[str, Any]],
    *,
    tolerance: int,
    source_text: str = "",
) -> list[list[Any]] | None:
    if len(groups) != len(candidates):
        return None
    reconciled = deepcopy(groups)
    for index, (group, candidate) in enumerate(zip(reconciled, candidates), start=1):
        target = _to_int(candidate.get("supply_price"))
        if target is None:
            return None
        actual = sum(_line_item_amount(item) or 0 for item in group)
        residual = target - actual
        if abs(residual) <= tolerance:
            continue
        reconstructed = _reconstruct_group_from_section_text(
            source_text,
            target_supply_amount=target,
            option_index=index,
            tolerance=tolerance,
        )
        if reconstructed:
            group[:] = reconstructed
            continue
        if residual <= 0 or residual > int(target * 0.30):
            return None
        group.append(
            LineItem(
                name="미파싱 옵션 잔액",
                category=LineItemCategory.ETC,
                quantity=1.0,
                unit="",
                unit_price=residual,
                total_price=residual,
                spec_raw=f"옵션 {index} 표에서 개별 품목으로 복원되지 않은 금액",
                spec_parsed={
                    "normalized_cost_type": "ETC",
                    "reconciliation_residual": True,
                    "evidence": {
                        "source": "option_candidate_minus_group_sum",
                        "candidate_supply_price": target,
                        "parsed_group_sum": actual,
                    },
                },
                extraction_confidence=0.3,
            )
        )
    return reconciled if _groups_match_candidates(reconciled, candidates, tolerance=tolerance) else None


def _reconstruct_group_from_section_text(
    source_text: str,
    *,
    target_supply_amount: int,
    option_index: int,
    tolerance: int,
) -> list[LineItem] | None:
    lines = _clean_section_lines(source_text)
    section = _find_section_by_subtotal(lines, target_supply_amount)
    if not section:
        return None
    items = _items_from_amount_triples(section, option_index=option_index)
    if not items:
        return None
    total = sum(_line_item_amount(item) or 0 for item in items)
    if abs(total - target_supply_amount) > tolerance:
        return None
    return items


def _clean_section_lines(source_text: str) -> list[str]:
    result = []
    for raw in (source_text or "").splitlines():
        line = re.sub(r"\s+", " ", str(raw)).strip(" \t|")
        if line:
            result.append(line)
    return result


def _find_section_by_subtotal(lines: list[str], target_supply_amount: int) -> list[str] | None:
    for idx, line in enumerate(lines):
        if re.sub(r"\s+", "", line) not in {"소계", "소계:"}:
            continue
        amount = _amount_near(lines, idx + 1)
        if amount != target_supply_amount:
            continue
        start = _section_start(lines, idx)
        return lines[start:idx]
    return None


def _amount_near(lines: list[str], start: int) -> int | None:
    for line in lines[start:start + 3]:
        amount = _parse_amount_text(line)
        if amount is not None:
            return amount
    return None


def _section_start(lines: list[str], subtotal_index: int) -> int:
    header_hits = 0
    for idx in range(subtotal_index - 1, -1, -1):
        compact = re.sub(r"\s+", "", lines[idx]).lower()
        if compact in {"비고", "견적금액", "견적단가", "수량", "상세내역", "품목", "번호"}:
            header_hits += 1
            if header_hits >= 4:
                return idx + 1
        if "소계" in compact or "합계" in compact:
            return idx + 1
    return 0


def _items_from_amount_triples(section_lines: list[str], *, option_index: int) -> list[LineItem]:
    triples = []
    for idx in range(len(section_lines) - 2):
        quantity = _parse_quantity_text(section_lines[idx])
        unit_price = _parse_amount_text(section_lines[idx + 1])
        supply = _parse_amount_text(section_lines[idx + 2])
        if quantity is None or unit_price is None or supply is None:
            continue
        if int(quantity * unit_price) != supply:
            continue
        name_index = _find_item_name_index(section_lines, idx)
        if name_index is None:
            continue
        next_name_index = _find_next_row_start(section_lines, idx + 3)
        spec_lines = _spec_lines_for_item(section_lines, name_index, idx, next_name_index)
        name = _normalize_reconstructed_item_name(section_lines[name_index], section_lines, name_index)
        item = LineItem(
            name=name,
            category=_initial_category_for_name(name),
            quantity=float(quantity),
            unit="",
            unit_price=unit_price,
            total_price=supply,
            spec_raw=" ".join(spec_lines).strip(),
            spec_parsed={
                "reconstructed_from_section": True,
                "reconstruction_source": "subtotal_section_amount_triples",
                "option_index": option_index,
            },
            extraction_confidence=0.78,
        )
        _attach_reconstructed_display_specs(item)
        normalize_line_item_category(item)
        triples.append((idx, item))
    return _dedupe_reconstructed_items([item for _, item in triples])


def _find_item_name_index(lines: list[str], quantity_index: int) -> int | None:
    descriptor = _previous_descriptive_line(lines, quantity_index)
    if descriptor is None:
        return None
    descriptor_text = lines[descriptor]
    if "수량" in descriptor_text and _previous_display_parent(lines, descriptor) is not None:
        return _previous_display_parent(lines, descriptor)
    if _looks_like_model_only(descriptor_text) and _previous_display_parent(lines, descriptor) is not None:
        return _previous_display_parent(lines, descriptor)
    return descriptor


def _previous_descriptive_line(lines: list[str], start: int) -> int | None:
    for idx in range(start - 1, -1, -1):
        line = lines[idx]
        if _is_numeric_line(line) or _parse_amount_text(line) is not None:
            continue
        compact = re.sub(r"\s+", "", line).lower()
        if compact in {"너비", "길이", "비고", "견적금액", "견적단가", "수량", "상세내역", "품목", "번호"}:
            continue
        if "전체" in compact and "수량" in compact:
            continue
        return idx
    return None


def _previous_display_parent(lines: list[str], start: int) -> int | None:
    for idx in range(start - 1, max(-1, start - 24), -1):
        text = lines[idx].lower()
        if "led display" in text or "전광판" in text or "display" in text or "비디오월" in text or "video wall" in text:
            return idx
    return None


def _find_next_row_start(lines: list[str], start: int) -> int:
    for idx in range(start, len(lines)):
        if _parse_quantity_text(lines[idx]) is not None:
            continue
        compact = re.sub(r"\s+", "", lines[idx]).lower()
        if compact in {"소계", "부가세", "합계"}:
            return idx
        if re.match(r"^\d{1,2}\s+\S", lines[idx]) and _parse_amount_text(lines[idx]) is None:
            return idx
        if _is_row_number_line(lines[idx]) and idx + 1 < len(lines):
            return idx
    return len(lines)


def _spec_lines_for_item(lines: list[str], name_index: int, quantity_index: int, next_name_index: int) -> list[str]:
    spec = []
    for idx in range(name_index + 1, quantity_index):
        if idx > name_index + 1 and _looks_like_numbered_item_start(lines[idx]):
            break
        if not _looks_like_currency_amount_line(lines[idx]):
            spec.append(_trim_inline_next_item_start(lines[idx]))
    for idx in range(quantity_index + 3, next_name_index):
        if _looks_like_numbered_item_start(lines[idx]):
            break
        if not _looks_like_currency_amount_line(lines[idx]):
            spec.append(_trim_inline_next_item_start(lines[idx]))
    return spec


def _trim_inline_next_item_start(line: str) -> str:
    parts = re.split(
        r"\s+\d{1,2}\s+(?=(?:All-in-one|브라켓|설치비|제품\s*설치비|예비품|SMPS|수신카드|충북|[A-Z]{2,}[-_]))",
        line,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    return parts[0].strip()


def _looks_like_numbered_item_start(line: str) -> bool:
    return bool(
        re.match(
            r"^\d{1,2}\s+(?:All-in-one|브라켓|설치비|제품\s*설치비|예비품|SMPS|수신카드|충북|[A-Z]{2,}[-_])",
            line,
            flags=re.IGNORECASE,
        )
    )


def _normalize_reconstructed_item_name(name: str, lines: list[str], name_index: int) -> str:
    stripped = name.strip()
    if stripped == "LED 모듈" and _previous_named_line(lines, name_index, "예비품") is not None:
        return "LED 모듈 예비품"
    if "LED Display" in stripped:
        return "LED Display"
    if "출장" in stripped or "체류비" in stripped:
        return stripped.replace("(개당)", "").strip()
    if stripped == "All-in-one":
        next_line = lines[name_index + 1] if name_index + 1 < len(lines) else ""
        if next_line and not _is_numeric_line(next_line):
            return f"{stripped} {next_line}".strip()
    return stripped


def _previous_named_line(lines: list[str], start: int, keyword: str) -> int | None:
    for idx in range(start - 1, max(-1, start - 5), -1):
        if keyword in lines[idx]:
            return idx
    return None


def _initial_category_for_name(name: str) -> LineItemCategory:
    text = name.lower()
    if "display" in text or "비디오월" in text or "전광판" in text:
        return LineItemCategory.DISPLAY
    if "설치" in text:
        return LineItemCategory.INSTALL
    if "브라켓" in text or "구조물" in text:
        return LineItemCategory.MOUNT
    if "controller" in text or "vx" in text or "all-in-one" in text or "수신카드" in text:
        return LineItemCategory.PLAYER
    return LineItemCategory.ETC


def _attach_reconstructed_display_specs(item: LineItem) -> None:
    if item.category != LineItemCategory.DISPLAY and "display" not in item.name.lower():
        return
    text = f"{item.name} {item.spec_raw}"
    spec = dict(item.spec_parsed or {})
    pitch = re.search(r"pitch\s*(\d+(?:\.\d+)?)\s*mm", text, re.IGNORECASE)
    if pitch:
        spec["pixel_pitch_mm"] = float(pitch.group(1))
        spec["pitch_mm"] = float(pitch.group(1))
    module = re.search(r"LED\s*모듈\s*크기.*?(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", text)
    if module:
        spec["module_size_mm"] = f"{module.group(1)} x {module.group(2)}"
    cabinet = re.search(r"LED\s*함체\s*크기.*?(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", text)
    if cabinet:
        spec["cabinet_size_mm"] = f"{cabinet.group(1)} x {cabinet.group(2)}"
    screen = re.search(r"스크린\s*크기.*?(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", text)
    if screen:
        width = str(int(round(float(screen.group(1)) * 1000)))
        height = str(int(round(float(screen.group(2)) * 1000)))
        spec["screen_size_mm"] = f"{width} x {height}"
        spec["full_screen_size_mm"] = f"{width} x {height}"
    resolution = re.search(r"스크린\s*해상도.*?(\d{3,5})\s+(\d{3,5})", text)
    if resolution:
        spec["resolution"] = f"{resolution.group(1)} x {resolution.group(2)}"
    spec["normalized_cost_type"] = "DISPLAY"
    item.spec_parsed = spec


def _dedupe_reconstructed_items(items: list[LineItem]) -> list[LineItem]:
    result = []
    seen = set()
    for item in items:
        key = (item.name, item.total_price)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _parse_quantity_text(text: str) -> float | None:
    stripped = text.strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", stripped):
        return None
    return float(stripped)


def _parse_amount_text(text: str) -> int | None:
    stripped = text.strip().replace("₩", "").replace("￦", "").replace("\\", "").replace(" ", "")
    if not re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d{4,}", stripped):
        return None
    return int(stripped.replace(",", ""))


def _looks_like_currency_amount_line(text: str) -> bool:
    stripped = text.strip()
    return bool(re.search(r"[₩￦\\]", stripped) or re.fullmatch(r"\d{1,3}(?:,\d{3})+", stripped))


def _is_numeric_line(text: str) -> bool:
    return re.fullmatch(r"\d+(?:\.\d+)?", text.strip()) is not None


def _is_row_number_line(text: str) -> bool:
    if re.fullmatch(r"\d+", text.strip()) is None:
        return False
    return 0 < int(text.strip()) <= 50


def _looks_like_model_only(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if any(keyword in stripped.lower() for keyword in ["설치", "브라켓", "출장", "체류비", "display", "비디오월"]):
        return False
    return bool(re.search(r"[A-Z]{2,}\d", stripped)) and len(stripped.split()) <= 2


def _groups_have_residual(groups: list[list[Any]]) -> bool:
    return any(
        (getattr(item, "spec_parsed", {}) or {}).get("reconciliation_residual")
        for group in groups
        for item in group
    )
