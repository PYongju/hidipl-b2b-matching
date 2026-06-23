from __future__ import annotations

from typing import Any


SCORE_TIE_EPSILON = 0.01
RANK_SCORE_MISMATCH_MESSAGE = (
    "동일한 업무 룰 통과 그룹 내에서 후순위 후보의 종합 점수가 더 높아 "
    "추천 순위 검증이 필요합니다."
)


def validate_rank_score_consistency(
    items: list[Any],
    *,
    group_key: str | None = None,
    score_epsilon: float = SCORE_TIE_EPSILON,
) -> None:
    grouped: dict[tuple[Any, bool], list[Any]] = {}
    for item in items or []:
        rank = getattr(item, "rank", None)
        if rank is None:
            continue
        key = (
            _resolve_group_value(item, group_key),
            bool(getattr(item, "business_rule_passed", False)),
        )
        grouped.setdefault(key, []).append(item)

    for candidates in grouped.values():
        ordered = sorted(candidates, key=lambda item: int(getattr(item, "rank", 0) or 0))
        best_previous = None
        for item in ordered:
            score = _score(item)
            if score is None:
                continue
            if best_previous is not None:
                previous_score = _score(best_previous)
                if previous_score is not None and score > previous_score + score_epsilon:
                    _add_rank_score_critical_risk(
                        item,
                        compared_item=best_previous,
                        message=RANK_SCORE_MISMATCH_MESSAGE,
                    )
                    _add_rank_score_critical_risk(
                        best_previous,
                        compared_item=item,
                        message=RANK_SCORE_MISMATCH_MESSAGE,
                    )
            if best_previous is None or score > (_score(best_previous) or float("-inf")):
                best_previous = item


def get_critical_risks(item: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    direct = getattr(item, "critical_risks", None)
    metadata = getattr(item, "metadata", None)
    metadata_risks = metadata.get("critical_risks", []) if isinstance(metadata, dict) else []
    for source in [direct, metadata_risks]:
        if not isinstance(source, list):
            continue
        for risk in source:
            normalized = risk if isinstance(risk, dict) else {"message": str(risk)}
            if not _risk_exists(result, normalized):
                result.append(dict(normalized))
    return result


def get_critical_risk_messages(item: Any) -> list[str]:
    messages: list[str] = []
    for risk in get_critical_risks(item):
        message = str(risk.get("message") or "").strip()
        if message and message not in messages:
            messages.append(message)
    return messages


def _add_rank_score_critical_risk(
    item: Any,
    *,
    compared_item: Any,
    message: str,
) -> None:
    risk = {
        "type": "rank_score_mismatch",
        "severity": "critical",
        "message": message,
        "expected_order_basis": "final_score_desc_within_business_rule_group",
        "current_quote_id": getattr(item, "quote_id", None),
        "current_rank": getattr(item, "rank", None),
        "current_final_score": getattr(item, "final_score", None),
        "compared_quote_id": getattr(compared_item, "quote_id", None),
        "compared_rank": getattr(compared_item, "rank", None),
        "compared_final_score": getattr(compared_item, "final_score", None),
        "business_rule_passed": bool(getattr(item, "business_rule_passed", False)),
        "product_group": _resolve_group_value(item, "product_group"),
    }

    risks = getattr(item, "critical_risks", None)
    if isinstance(risks, list) and not _risk_exists(risks, risk):
        risks.append(dict(risk))

    metadata = getattr(item, "metadata", None)
    if isinstance(metadata, dict):
        metadata_risks = metadata.setdefault("critical_risks", [])
        if isinstance(metadata_risks, list) and not _risk_exists(metadata_risks, risk):
            metadata_risks.append(dict(risk))

    check_required = getattr(item, "check_required", None)
    if isinstance(check_required, list) and message not in check_required:
        check_required.append(message)


def _resolve_group_value(item: Any, group_key: str | None) -> Any:
    if not group_key:
        return None
    metadata = getattr(item, "metadata", None)
    if isinstance(metadata, dict) and group_key in metadata:
        return metadata.get(group_key)
    return getattr(item, group_key, None)


def _score(item: Any) -> float | None:
    value = getattr(item, "final_score", None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _risk_exists(risks: list[Any], risk: dict[str, Any]) -> bool:
    signature = (risk.get("type"), risk.get("message"))
    return any(
        isinstance(existing, dict)
        and (existing.get("type"), existing.get("message")) == signature
        for existing in risks
    )
