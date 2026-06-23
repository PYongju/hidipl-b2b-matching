"""
강화된 채점기 (v2).
====================
기존 v1 의 BANNED_PHRASES 단어 매칭에 더해, 입력↔출력 대조 기반 5가지 카테고리 검사를 추가.

추가 검사 카테고리:
  1. BANNED_PHRASES (기존)              — 과장 금칙어 ("최고 수준", "만점" 등)
  2. check_required 누락                 — 입력의 check_required 항목이 weaknesses 에 반영됐는가
  3. vendor_name/partner_name 추측      — 입력의 빈 값을 LLM 이 채워 넣었는가
  4. rank-score 모순 미명시              — rank 1 의 final_score 가 max 가 아닌데 LLM 이 침묵
  5. 점수 격차 무시                       — 격차 50+ 인데 "우수" 로 뭉뚱그림
  6. 빈 값 인용 (warranty/금액/납기)      — None 인 필드를 LLM 이 구체 숫자로 인용

[설계 원칙]
- 기존 evaluate() 의 raw/final/postprocess/fallback 통계 구조는 그대로 유지.
- raw_violation 의 의미를 확장: "위반 카테고리가 하나라도 발견되면 True".
- records 에 카테고리별 위반 내역을 같이 저장 (발표용 카테고리 통계 분석 가능).
"""

import json
import re
from collections import Counter

from services.explanation.factory import create_explanation_provider


# provider 값 분류 ----------------------------------------------------------
LLM_OK_PROVIDER = "azure_openai"

FALLBACK_PROVIDERS = {
    "azure_openai_fallback_template",
    "template_fallback",
    "template",
}

TEMPLATE_PROVIDER = "template"

# 검사 1: 기존 금칙어 ------------------------------------------------------
BANNED_PHRASES = (
    "과도히", "과도하게", "과도",
    "완전히", "완전",
    "최고 수준", "최고의",
    "만점", "정도도",
)

CRITICAL_KEYWORDS = (
    "비정상",       # 보증/납기/성공률 이상값
    "미기재",       # 가격/공급사명 공란
    "범위 밖",      # success_rate 등 범위 외
    "미매칭",       # 프리미엄·파트너 부조화
    "산정 불일치",  # 점수 가중합 불일치
    "순위 산정",       
    "rank 불일치",
)

# ============================================================
# 텍스트 유틸
# ============================================================
def _iter_str_values(obj):
    """dict/list 를 재귀 순회하며 문자열 값만 흘려보낸다."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_str_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_str_values(v)
    elif isinstance(obj, str):
        yield obj


def _sup_text(sup: dict) -> str:
    """supplier 항목의 모든 자유 텍스트를 한 덩어리로."""
    parts = [sup.get("card_summary", "")]
    parts.extend(sup.get("strengths", []) or [])
    parts.extend(sup.get("weaknesses", []) or [])
    # comparison_risks 추가 (문자열/리스트 둘 다)
    cr = sup.get("comparison_risks")
    if isinstance(cr, list):
        parts.extend(cr)
    elif isinstance(cr, str):
        parts.append(cr)
    return " ".join(str(p) for p in parts if p)

# ============================================================
# 카테고리별 검사 함수들
# ============================================================
def _check_banned(text: str) -> list[tuple]:
    """카테고리 1: 금칙어 매칭."""
    return [("banned_phrase", w) for w in BANNED_PHRASES if w in text]


def _check_required_missing(items: list[dict], suppliers: list[dict]) -> list[tuple]:
    """카테고리 2: check_required 항목이 weaknesses 에 반영됐는가.

    정책 (정밀화):
      - critical 항목 (CRITICAL_KEYWORDS 매칭) → 반드시 weaknesses 또는 comparison_risks 에 반영.
        critical 키워드 자체 (미기재/비정상/범위 밖/미매칭/산정 불일치/필터 사유/순위 산정) 가
        weakness 텍스트에 등장해야 통과. 단순 도메인 단어 (예: '총 공급가') 만 있어선 안 됨.
      - 일반 안내 항목 → 누락 허용. 검사 안 함.
    """
    out = []
    for it in items:
        cr_list = it.get("check_required") or []
        qid = it.get("quote_id")
        sup = next((s for s in suppliers if s.get("quote_id") == qid), None)
        if not sup or not cr_list:
            continue
        weak_text = "\n".join(sup.get("weaknesses", []) or [])
        # comparison_risks 는 문자열일 수도 리스트일 수도 있음 — 둘 다 처리
        cr = sup.get("comparison_risks") or ""
        if isinstance(cr, list):
            cr = "\n".join(str(x) for x in cr)
        weak_text += "\n" + cr
        
        for cr in cr_list:
            is_critical = any(kw in cr for kw in CRITICAL_KEYWORDS)
            if not is_critical:
                continue  # 일반 안내성 — 검사 안 함
            
            # critical 키워드 자체 (미기재 등) 가 weakness 에 직접 등장해야 통과
            critical_keyword_found = any(kw in weak_text for kw in CRITICAL_KEYWORDS)
            
            # 그리고 어떤 영역인지도 매칭 — "총 공급가 미기재" critical 이면 "총 공급가" 도 필요
            keywords = [w for w in re.findall(r"[가-힣A-Za-z0-9]+", cr) if len(w) >= 2]
            if not keywords:
                continue
            domain_found = any(k in weak_text for k in keywords[:3])
            
            # critical 키워드 + 도메인 키워드 둘 다 있어야 통과
            if not (critical_keyword_found and domain_found):
                out.append(("check_required_missing", qid, cr))
    return out

def _check_vendor_guess(items: list[dict], suppliers: list[dict]) -> list[tuple]:
    out = []
    # 같은 시나리오의 다른 아이템 업체명 목록 (유추 출처가 되는 이름들)
    all_vendor_names = {
        it.get("vendor_name") for it in items 
        if it.get("vendor_name")  # 비지 않은 것만
    }
    for it in items:
        qid = it.get("quote_id")
        sup = next((s for s in suppliers if s.get("quote_id") == qid), None)
        if not sup:
            continue
        if it.get("vendor_name") in (None, ""):
            if sup.get("vendor_name") and sup.get("vendor_name") not in ("", "미상", "불명", "업체 미확인", "확인 필요"):
                out.append(("vendor_guess", qid, sup.get("vendor_name")))
                continue
        # 텍스트에서도 다른 아이템의 업체명이 언급됐는지
            sup_text = _sup_text(sup)
            for other_name in all_vendor_names:
                if other_name and len(other_name) >= 2 and other_name in sup_text:
                    out.append(("vendor_guess_from_context", qid, other_name))
                    break
    return out


def _check_rank_score_mismatch(items, all_text):
    scores = [it.get("final_score") for it in items if it.get("final_score") is not None]
    if len(scores) < 2:
        return []
    if scores[0] >= max(scores):
        return []
    
    # rank-score 모순 명시 정확히 확인 — "순위"와 "점수"가 같은 문맥에서 함께
    # 또는 명확한 불일치 표현
    clear_mention_patterns = [
        ("순위", "점수", "불일치"),          # "순위와 점수 불일치"
        ("순위", "점수", "낮"),               # "순위 1위이나 점수가 낮음"
        ("순위", "점수", "높"),               # "순위 N위이나 점수는 높음"
        ("rank", "score", "mismatch"),
        ("산정 기준 확인",),                  # critical 메시지 그대로
        ("순위와 점수",),                     # 명확한 표현
    ]
    
    for patterns in clear_mention_patterns:
        if all(p in all_text for p in patterns):
            return []  # 명확히 명시함 → 통과
    
    return [("rank_score_mismatch", scores)]


def _check_score_gap(items: list[dict], all_text: str) -> list[tuple]:
    """카테고리 5: 점수 격차가 50+ 인데 묶음 표현으로 가림.
    
    새 프롬프트 정책:
      - 묶음 표현 ('둘 다 우수', '모두 우수') → 위반
      - 분리 표현 ('가장 우수' vs '낮은 편') 또는 격차 명시 → OK
    """
    scores = [it.get("final_score") for it in items if it.get("final_score") is not None]
    if len(scores) < 2:
        return []
    gap = max(scores) - min(scores)
    if gap <= 50:
        return []
    
    # 묶음 표현 — 위반 신호
    bad_patterns = (
        "모두 우수", "둘 다 우수", "함께 우수", "공통적으로 우수",
        "모두 양호", "둘 다 양호",
        "상위 두 후보 모두",
    )
    # 분리 표현 또는 격차 인지 — OK 신호
    good_patterns = (
        "가장 우수", "최상위", "상위", 
        "낮은 편", "열세", "다소 낮", "상대적으로 낮",
        "큰 차이", "두드러진", "상당한", "격차",
    )
    
    has_bad = any(p in all_text for p in bad_patterns)
    has_good = any(p in all_text for p in good_patterns)
    
    if has_bad:
        return [("score_gap_ignored", round(gap, 1))]
    # 묶음 표현 없고 분리/격차 표현이 있으면 OK
    if has_good:
        return []
    # 둘 다 없는데 "우수"가 있으면 의심 (보수적으로 위반)
    if "우수" in all_text:
        return [("score_gap_ignored", round(gap, 1))]
    return []


def _check_empty_value_quoting(items: list[dict], suppliers: list[dict]) -> list[tuple]:
    """카테고리 6: warranty/total_with_vat/delivery_weeks 가 None 인데 LLM 이 구체 숫자 인용.
    
    정밀화:
      - total_with_vat 가 None 이어도 total_supply_price 정확 인용은 OK.
        LLM 이 다른 가격 숫자를 '계산해서' 만들어 인용하면 환각.
    """
    out = []
    for it in items:
        qid = it.get("quote_id")
        sup = next((s for s in suppliers if s.get("quote_id") == qid), None)
        if not sup:
            continue
        sup_text = _sup_text(sup)
        
        # 보증 None 인데 구체 개월수 인용
        if it.get("warranty_months") is None:
            m = re.search(r"보증.{0,5}(\d+)\s*(개월|년)", sup_text)
            if m:
                out.append(("warranty_guess", qid, m.group()))
        
        # 금액 None 인데 LLM 이 다른 가격 숫자를 "계산해서" 인용 = 환각
        # total_supply_price 정확한 인용은 OK.
        if it.get("total_with_vat") is None:
            legit = it.get("total_supply_price")
            found_prices = re.findall(r"(\d[\d,]*)\s*(?:만원|원)", sup_text)
            for p_str in found_prices:
                p_num = int(p_str.replace(",", ""))
                if legit:
                    legit_man = legit // 10000
                    legit_won = legit
                    if p_num == legit_man or p_num == legit_won:
                        continue
                out.append(("price_guess", qid, p_str))
                break
        
        # 납기 None 인데 구체 주수 인용
        if it.get("delivery_weeks") is None:
            m = re.search(r"납기.{0,5}(\d+)\s*(주|일)", sup_text)
            if m:
                out.append(("delivery_guess", qid, m.group()))
    return out

def _check_weakness_count(suppliers: list[dict], max_count: int = 2) -> list[tuple]:
    """카테고리 7: weaknesses 가 정확히 2개를 초과하면 위반.
    
    새 프롬프트 정책: weaknesses 정확히 2개. 3개 이상 절대 금지.
    """
    out = []
    for sup in suppliers:
        ws = sup.get("weaknesses", []) or []
        if len(ws) > max_count:
            out.append(("weakness_too_many", sup.get("quote_id"), len(ws)))
    return out


# ============================================================
# 통합 검사기
# ============================================================
def is_violation_v2(raw_llm_output: str, rec=None) -> tuple[bool, list]:
    """v2: 입력(rec)↔출력(raw) 대조 기반 6 카테고리 검사.

    Args:
        raw_llm_output: LLM 의 후처리 전 원본 JSON 문자열.
        rec: 입력 RecommendationPipelineResult (items 등 참조용). None 이면 카테고리 1만.

    Returns:
        (위반 여부, 위반 내역 리스트).
        위반 내역의 각 원소는 ("카테고리_이름", ...상세...) 튜플.
    """
    violations: list = []

    # 카테고리 1: 금칙어 (raw 전체 텍스트에서)
    text_to_check = raw_llm_output
    try:
        parsed = json.loads(raw_llm_output)
        text_to_check = " ".join(_iter_str_values(parsed))
    except (json.JSONDecodeError, TypeError):
        parsed = None
    violations.extend(_check_banned(text_to_check))

    # rec 없으면 카테고리 1만으로 종료 (기존 v1 호환)
    if rec is None or parsed is None:
        return (len(violations) > 0, violations)

    suppliers = parsed.get("supplier_explanations", []) or []
    # rec.items 가 dataclass 면 dict 화 (items 가 RecommendationItem 객체일 수 있음)
    items_raw = rec.items[:3] if rec.items else []
    items = []
    for it in items_raw:
        if isinstance(it, dict):
            items.append(it)
        else:
            # dataclass → dict
            from dataclasses import asdict, is_dataclass
            items.append(asdict(it) if is_dataclass(it) else vars(it))

    all_text = " ".join(_sup_text(s) for s in suppliers)
    overall = parsed.get("overall_summary", "") or ""
    all_text = overall + " " + all_text

    # 카테고리 2~6
    violations.extend(_check_required_missing(items, suppliers))
    violations.extend(_check_vendor_guess(items, suppliers))
    violations.extend(_check_rank_score_mismatch(items, all_text))
    violations.extend(_check_score_gap(items, all_text))
    violations.extend(_check_empty_value_quoting(items, suppliers))
    violations.extend(_check_weakness_count(suppliers))

    return (len(violations) > 0, violations)


# ============================================================
# 기존 v1 함수 — 후방 호환용으로 남김 (다른 코드가 import 하면 안 깨지게)
# ============================================================
def is_violation(raw_llm_output: str) -> bool:
    """v1: BANNED_PHRASES 만 검사 (기존 동작)."""
    text_to_check = raw_llm_output
    try:
        parsed = json.loads(raw_llm_output)
        text_to_check = " ".join(_iter_str_values(parsed))
    except (json.JSONDecodeError, TypeError):
        pass
    return any(phrase in text_to_check for phrase in BANNED_PHRASES)


def _final_output_has_violation(result) -> bool:
    """참고 지표: 후처리 후 최종 필드 기준 위반 (기존 그대로 — 금칙어만)."""
    fields = [result.overall_summary]
    for s in result.supplier_explanations:
        if s.metadata.get("fallback_used"):
            continue
        fields.append(s.card_summary)
        fields.extend(s.strengths)
        fields.extend(s.weaknesses)
    joined = " ".join(str(f) for f in fields)
    return any(phrase in joined for phrase in BANNED_PHRASES)


# ============================================================
# evaluate (v2 검사기 통합)
# ============================================================
def evaluate(eval_dataset, settings) -> dict:
    """v2 평가 실행: 6 카테고리 검사 + 기존 raw/final/postprocess/fallback 지표.

    raw_violation 의 의미 확장:
      - v1: BANNED_PHRASES 매칭이면 True
      - v2: 6 카테고리 중 하나라도 위반이면 True

    records 에 새 필드 추가:
      - violation_categories: [("banned_phrase","최고 수준"), ("check_required_missing","M-02","..."), ...]
    """
    provider = create_explanation_provider(
        "azure_openai",
        settings=settings,
        capture_raw_output=True,
    )

    # 주 지표 / 후처리 보정 / 참고 지표 / 안정성/폴백 (기존 구조 유지)
    total_llm = 0
    violations_raw = 0
    postprocess_corrected_count = 0
    final_total = 0
    final_violations = 0
    partial_fallback_records = 0
    raw_output_missing_count = 0
    fallback_by_provider = Counter()
    config_errors = 0
    records = []

    # 옵션 B: 폴백 실패 유형 분리
    json_parse_failed_count = 0
    llm_call_failed_count = 0
    truncated_count = 0

    # v2 추가: 카테고리별 위반 건수 집계
    category_counter = Counter()

    for rec in eval_dataset:
        result = provider.generate(rec)
        raw = result.raw_llm_output
        qid = rec.items[0].quote_id if rec.items else "?"

        # --- raw 없는 케이스: 주 지표에서 제외 (기존 그대로) ---
        if raw is None:
            raw_output_missing_count += 1
            if result.provider == LLM_OK_PROVIDER:
                config_errors += 1
                print(
                    "[CONFIG WARNING] provider=azure_openai 인데 raw_llm_output 이 None "
                    f"(request_id={result.request_id}). "
                    "capture_raw_output=True 설정 여부를 확인하세요."
                )
            elif result.provider in FALLBACK_PROVIDERS:
                fallback_by_provider[result.provider] += 1
                error_type = result.metadata.get("fallback_error_type")
                if error_type == "json_parse":
                    json_parse_failed_count += 1
                elif error_type == "api_call":
                    llm_call_failed_count += 1
                elif error_type == "truncated":
                    truncated_count += 1
            else:
                config_errors += 1
                print(
                    f"[CONFIG WARNING] 분류되지 않은 provider={result.provider!r}, raw=None "
                    f"(request_id={result.request_id})."
                )

            records.append({
                "quote_id": qid,
                "raw_violation": None,
                "final_violation": None,
                "provider": result.provider,
                "raw_output": None,
                "violation_categories": [],
                "note": "raw_missing",
            })
            continue

        # --- 주 지표 (v2: 6 카테고리 검사) ---
        total_llm += 1
        raw_viol, viol_list = is_violation_v2(raw, rec=rec)
        if raw_viol:
            violations_raw += 1
            for v in viol_list:
                category_counter[v[0]] += 1

        # --- 참고 지표 (final 기준 — 기존 금칙어만, 후처리 효과 측정용) ---
        final_total += 1
        final_viol = _final_output_has_violation(result)
        if final_viol:
            final_violations += 1
        if any(s.metadata.get("fallback_used") for s in result.supplier_explanations):
            partial_fallback_records += 1

        # 후처리 보정 (raw 위반 ∧ final 클린)
        if raw_viol and not final_viol:
            postprocess_corrected_count += 1

        records.append({
            "quote_id": qid,
            "raw_violation": raw_viol,
            "final_violation": final_viol,
            "provider": result.provider,
            "raw_output": raw,
            "violation_categories": viol_list,   # v2 신규
        })

    # --- 비율 계산 (기존 그대로) ---
    total_records = total_llm + raw_output_missing_count
    fallback_total = sum(fallback_by_provider.values())
    template_provider_count = fallback_by_provider.get(TEMPLATE_PROVIDER, 0)

    violation_rate_primary = (violations_raw / total_llm) if total_llm else None
    violation_rate_final = (final_violations / final_total) if final_total else None
    fallback_rate = (fallback_total / total_records) if total_records else None
    postprocess_correction_rate = (
        (postprocess_corrected_count / violations_raw) if violations_raw else None
    )

    return {
        # 주 지표 (raw 기준, v2 강화)
        "violation_rate_primary": violation_rate_primary,
        "total_llm": total_llm,
        "violations_raw": violations_raw,
        # v2 추가: 카테고리별 위반 건수
        "violations_by_category": dict(category_counter),
        # 후처리 보정 (final 기준은 여전히 금칙어만 — 후처리는 _clean_text 가 금칙어만 다루니까)
        "postprocess_corrected_count": postprocess_corrected_count,
        "postprocess_correction_rate": postprocess_correction_rate,
        # 참고 지표 (final 기준 — 금칙어만)
        "violation_rate_final": violation_rate_final,
        "final_total": final_total,
        "final_violations": final_violations,
        "partial_fallback_records": partial_fallback_records,
        # 안정성/폴백
        "raw_output_missing_count": raw_output_missing_count,
        "fallback_rate": fallback_rate,
        "fallback_by_provider": dict(fallback_by_provider),
        "template_provider_count": template_provider_count,
        "json_parse_failed_count": json_parse_failed_count,
        "llm_call_failed_count": llm_call_failed_count,
        "truncated_count": truncated_count,
        "config_errors": config_errors,
        # 메타
        "total_records": total_records,
        "records": records,
    }


if __name__ == "__main__":
    pass
