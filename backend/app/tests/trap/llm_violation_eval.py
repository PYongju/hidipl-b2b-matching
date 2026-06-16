"""

[주의] is_violation은 현재 '_clean_text가 치환하는 금칙어'만 검사한다.
       업체명/금액/점수 날조 같은 넓은 의미의 환각은 별도 검사로 확장 필요(아래 TODO).
"""

import json
from collections import Counter

from services.explanation.factory import create_explanation_provider


# provider 값 분류 ----------------------------------------------------------
LLM_OK_PROVIDER = "azure_openai"  # 정상 LLM 산출(원본 존재 기대)

FALLBACK_PROVIDERS = {            # LLM 원본 없음 → 정상 폴백(방안 A: 주 지표 모수 제외)
    "azure_openai_fallback_template",  # provider 내부 LLM 호출/파싱 실패(둘 합쳐짐 — 추후 분리 논의)
    "template_fallback",               # 라우터 단계 폴백
    "template",                        # 애초에 LLM 미사용(실패 아님)
}

TEMPLATE_PROVIDER = "template"     # 'LLM 미사용' — 실패와 구분해 따로 보고

# _clean_text 치환 대상과 동일한 금칙어 집합(원본 기준 위반 판정용)
BANNED_PHRASES = (
    "과도히", "과도하게", "과도",
    "완전히", "완전",
    "최고 수준", "최고의",
    "만점", "정도도",
)


def _iter_str_values(obj):
    """dict/list를 재귀 순회하며 '문자열 값'만 흘려보낸다(키 이름은 제외)."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_str_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_str_values(v)
    elif isinstance(obj, str):
        yield obj


def is_violation(raw_llm_output: str) -> bool:
    """후처리 전 원본(raw) 기준 금칙어 위반 검사.

    raw는 모델이 낸 JSON 문자열 전체다. 파싱되면 '값 텍스트'만 모아 검사해
    JSON 키/구조로 인한 false positive를 줄인다. 파싱 실패 시엔 보수적으로 원문 전체를 검사한다.
    """
    text_to_check = raw_llm_output
    try:
        parsed = json.loads(raw_llm_output)
        text_to_check = " ".join(_iter_str_values(parsed))
    except (json.JSONDecodeError, TypeError):
        pass  # 파싱 실패 → 원문 전체로 검사(누락보다 과검출이 안전)
    return any(phrase in text_to_check for phrase in BANNED_PHRASES)


def _final_output_has_violation(result) -> bool:
    """참고 지표: 후처리 후 최종 필드 기준 위반 검사.

    부분 폴백으로 템플릿이 채운 supplier는 LLM 산출이 아니므로 판정 대상에서 제외한다.
    정상 동작이라면 _clean_text가 금칙어를 치환하므로 이 값은 보통 0에 수렴한다.
    (주 지표가 높은데 이 값이 0이면 = '후처리가 위반을 가린다'는 메모의 핵심 근거.)
    """
    fields = [result.overall_summary]
    for s in result.supplier_explanations:
        if s.metadata.get("fallback_used"):
            continue  # 템플릿 산출 supplier → LLM 위반 판정 대상 아님
        fields.append(s.card_summary)
        fields.extend(s.strengths)
        fields.extend(s.weaknesses)
    joined = " ".join(str(f) for f in fields)
    return any(phrase in joined for phrase in BANNED_PHRASES)


def evaluate(eval_dataset, settings) -> dict:
    """방안 A 평가 실행.

    Args:
        eval_dataset: RecommendationPipelineResult 들의 이터러블.
        settings: Azure OpenAI 설정 객체.

    Returns:
        주 지표 / 후처리 보정 / 참고 지표 / 안정성(폴백) 지표를 담은 report dict.
    """
    provider = create_explanation_provider(
        "azure_openai",
        settings=settings,
        capture_raw_output=True,  # 평가 모드 필수
    )

    # 주 지표(방안 A: raw 존재 건만) -----------------------------------------
    total_llm = 0          # 분모: 원본이 실제 존재한 건수
    violations_raw = 0     # 분자: 원본 기준 위반 건수

    # 후처리 보정(가림) 측정 --------------------------------------------------
    postprocess_corrected_count = 0  # raw에선 위반 ∧ final은 클린 → 후처리가 가린 건수

    # 참고 지표(후처리 후 최종 기준) + 부분 폴백 추적 -------------------------
    final_total = 0
    final_violations = 0
    partial_fallback_records = 0  # LLM 호출은 됐으나 일부 supplier가 템플릿으로 채워진 건수

    # 안정성/폴백(별도 보고) --------------------------------------------------
    raw_output_missing_count = 0      # raw가 None이라 주 지표에서 제외된 전체 건수
    fallback_by_provider = Counter()  # provider 종류별 폴백 건수
    config_errors = 0
    records = []                 # azure_openai인데 raw=None 등 비정상(0이어야 정상)

    # 폴백 실패 유형 분리(옵션 B: provider 의 metadata["fallback_error_type"] 기준) ----------
    json_parse_failed_count = 0
    llm_call_failed_count = 0
    truncated_count = 0

    for rec in eval_dataset:
        result = provider.generate(rec)
        raw = result.raw_llm_output
        qid = rec.items[0].quote_id if rec.items else "?"


        # --- raw 없는 케이스: 주 지표에서 제외(방안 A) ---
        if raw is None:
            raw_output_missing_count += 1
            if result.provider == LLM_OK_PROVIDER:
                # 정상 폴백이 아님: capture_raw_output 누락 의심 → 조용히 묻지 않고 경고
                config_errors += 1
                print(
                    "[CONFIG WARNING] provider=azure_openai 인데 raw_llm_output 이 None "
                    f"(request_id={result.request_id}). "
                    "capture_raw_output=True 설정 여부를 확인하세요."
                )
            elif result.provider in FALLBACK_PROVIDERS:
                fallback_by_provider[result.provider] += 1  # 종류별 집계
                # 옵션 B: provider 가 명시한 실패 유형으로 분리 (문자열 매칭 아님)
                error_type = result.metadata.get("fallback_error_type")
                if error_type == "json_parse":
                    json_parse_failed_count += 1
                elif error_type == "api_call":
                    llm_call_failed_count += 1
                elif error_type == "truncated":
                    truncated_count += 1
                # postprocess/unknown/None 은 fallback_by_provider 로만 집계
            else:
                # 예상 못 한 provider 값 → 가시화(분류 누락 방지)
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
                "note": "raw_missing",
            })

            continue

        # --- 주 지표 (방안 A) ---
        total_llm += 1
        raw_viol = is_violation(raw)
        if raw_viol:
            violations_raw += 1

        # --- 참고 지표 + 부분 폴백 추적 ---
        final_total += 1
        final_viol = _final_output_has_violation(result)
        if final_viol:
            final_violations += 1
        if any(s.metadata.get("fallback_used") for s in result.supplier_explanations):
            partial_fallback_records += 1

        # --- 후처리 보정(가림) 측정: raw 위반인데 final 클린 ---
        if raw_viol and not final_viol:
            postprocess_corrected_count += 1
        
        records.append({
            "quote_id": qid,
            "raw_violation": raw_viol,
            "final_violation": final_viol,
            "provider": result.provider,
            "raw_output": raw,
        })

    # --- 비율 계산: 분모 0 방어 ---
    total_records = total_llm + raw_output_missing_count  # 처리한 전체 건수(generator 안전)
    fallback_total = sum(fallback_by_provider.values())
    template_provider_count = fallback_by_provider.get(TEMPLATE_PROVIDER, 0)

    violation_rate_primary = (violations_raw / total_llm) if total_llm else None
    violation_rate_final = (final_violations / final_total) if final_total else None
    fallback_rate = (fallback_total / total_records) if total_records else None
    # 후처리 보정율 정의: '원본 위반 중 후처리가 가린 비율'
    postprocess_correction_rate = (
        (postprocess_corrected_count / violations_raw) if violations_raw else None
    )

    return {
        # 주 지표 (raw 기준) ----------------------------------------------
        "violation_rate_primary": violation_rate_primary,
        "total_llm": total_llm,
        "violations_raw": violations_raw,
        # 후처리 보정(가림) ------------------------------------------------
        "postprocess_corrected_count": postprocess_corrected_count,
        "postprocess_correction_rate": postprocess_correction_rate,
        # 참고 지표 (후처리 후 최종 기준) ----------------------------------
        "violation_rate_final": violation_rate_final,
        "final_total": final_total,
        "final_violations": final_violations,
        "partial_fallback_records": partial_fallback_records,
        # 안정성/폴백 (별도 보고) ------------------------------------------
        "raw_output_missing_count": raw_output_missing_count,
        "fallback_rate": fallback_rate,
        "fallback_by_provider": dict(fallback_by_provider),
        "template_provider_count": template_provider_count,
        "config_errors": config_errors,  # 0이 아니면 평가 설정 점검 필요
        # 메타 ------------------------------------------------------------
        "total_records": total_records,
        "records": records,
    }


if __name__ == "__main__":
    # 사용 예시 (실제 settings / eval_dataset 로딩은 환경에 맞게 연결)
    #
    # from services.config import get_settings
    # report = evaluate(eval_dataset, get_settings())
    # print(json.dumps(report, ensure_ascii=False, indent=2))
    #
    # 보고서 작성 시 반드시 명시(메모 §3 경고):
    #   - raw 없는 케이스 제외 방식(방안 A) + raw_output_missing_count / fallback_by_provider 내역
    #   - 주 지표(raw)·참고 지표(final)·후처리 보정율을 분리해 해석
    #   - config_errors는 0이어야 정상(0이 아니면 capture 플래그/설정 점검)
    #
    # TODO(환각 확장): is_violation은 금칙어 치환 대상만 검사. 업체명/금액/점수 날조 검출은
    #   입력(quote_id, vendor_name, score 등)과 raw를 대조하는 검사로 별도 추가 필요.
    pass
