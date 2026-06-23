"""
본 실행: 함정 8건 + 대조군 8건 채점.
실행: (backend/app 에서)  python -m tests.trap.main_run
산출: tests/trap/reports/main_run_{timestamp}.json
 
[v2 검사기 사용]
- llm_violation_eval_v2.evaluate 호출
- 6 카테고리 위반 검사 (BANNED_PHRASES + check_required_missing + rank_score_mismatch
  + score_gap_ignored + vendor_guess + 빈 값 인용)
- 새 프롬프트 정책 (점수 숫자 직접 인용 금지, weakness 정확히 2개, 같은 영역 묶기) 와 일치
- records 에 violation_categories 같이 저장 → 케이스별 어떤 위반인지 명확히
"""
import datetime
import json
import os
 
from tests.trap.baseline_loader import get_normal_result
from tests.trap.trap_injection_verify import run_injection_check
# v2 검사기로 변경 (이전: llm_violation_eval)
from tests.trap.llm_violation_eval_v2 import evaluate
from services.explanation.explanation_input_builder import build_explanation_input
from services.config import get_settings
 
 
QIDS = ["M-02", "M-10", "M-15", "V-01", "V-02", "V-05", "V-09", "V-15"]
 
 
def _fmt_category(v: list) -> str:
    """위반 카테고리 튜플 한 줄로 보기 좋게."""
    cat = v[0]
    if cat == "banned_phrase":
        return f"금칙어 '{v[1]}'"
    if cat == "check_required_missing":
        # ('check_required_missing', qid, message)
        msg = v[2] if len(v) > 2 else "?"
        return f"check_required 누락 ({v[1]}): {msg[:50]}"
    if cat == "rank_score_mismatch":
        scores = v[1] if len(v) > 1 else "?"
        return f"rank-score 모순 미명시 (rank순 final_score={scores})"
    if cat == "score_gap_ignored":
        gap = v[1] if len(v) > 1 else "?"
        return f"점수 격차 무시 (격차 {gap}점, '우수' 묶음 표현)"
    if cat == "vendor_guess":
        return f"vendor_name 추측 ({v[1]}): LLM 응답에 '{v[2] if len(v) > 2 else '?'}' 채워 넣음"
    if cat == "partner_guess":
        return f"partner_name 추측 ({v[1]})"
    if cat == "warranty_guess":
        return f"보증 추측 ({v[1]})"
    if cat == "price_guess":
        return f"금액 추측 ({v[1]})"
    if cat == "delivery_guess":
        return f"납기 추측 ({v[1]})"
    if cat == "weakness_too_many":
        return f"weakness 개수 초과 ({v[1]}): {v[2]}개 작성 (max 2 정책 위반)"
    
    return str(v)
 
def main() -> None:
    settings = get_settings()
 
    # === (A) 함정 그룹 ===
    print("\n=== (A) 함정 8건 채점 시작 ===")
    trap_dataset, ok = run_injection_check(get_normal_result, build_explanation_input)
    assert ok, "1차 게이트 실패 — baseline/패치 점검 필요"
    report_trap = evaluate(trap_dataset, settings)
    print(f"  함정 그룹 채점 완료. total_llm={report_trap.get('total_llm')}")
 
    # === (B) 대조군 (패치 없이 baseline 그대로) ===
    print("\n=== (B) 대조군 8건 채점 시작 ===")
    clean_dataset = [get_normal_result(qid) for qid in QIDS]
    report_clean = evaluate(clean_dataset, settings)
    print(f"  대조군 채점 완료. total_llm={report_clean.get('total_llm')}")
 
    # === 결과 저장 ===
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(out_dir, exist_ok=True)
 
    out = {
        "timestamp": ts,
        "trap": report_trap,
        "clean": report_clean,
    }
    out_path = os.path.join(out_dir, f"main_run_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
 
    # === 핵심 지표 요약 ===
    print("\n" + "=" * 70)
    print("핵심 지표 요약 (v2: 6 카테고리 검사)")
    print("=" * 70)
    print(f"{'':32} {'함정':>14}  {'대조군':>14}")
    keys = [
        ("total_llm", "total_llm"),
        ("violation_rate_primary", "위반율(raw, 주지표)"),
        ("violation_rate_final", "위반율(final, 금칙어만)"),
        ("postprocess_correction_rate", "후처리 보정율"),
        ("raw_output_missing_count", "raw 누락"),
        ("fallback_rate", "폴백율"),
        ("config_errors", "config_errors"),
    ]
    for k, label in keys:
        tv = report_trap.get(k, "?")
        cv = report_clean.get(k, "?")
        if isinstance(tv, float):
            tv = f"{tv:.3f}"
        if isinstance(cv, float):
            cv = f"{cv:.3f}"
        print(f"{label:32} {str(tv):>14}  {str(cv):>14}")
 
    # === 카테고리별 위반 통계 (v2 신규) ===
    print("\n" + "=" * 70)
    print("카테고리별 위반 통계")
    print("=" * 70)
    print(f"{'카테고리':32} {'함정':>14}  {'대조군':>14}")
    t_cat = report_trap.get("violations_by_category", {})
    c_cat = report_clean.get("violations_by_category", {})
    all_cats = sorted(set(t_cat) | set(c_cat))
    if not all_cats:
        print("  (위반 0건 — 환각 검출 없음)")
    else:
        for cat in all_cats:
            tv = t_cat.get(cat, 0)
            cv = c_cat.get(cat, 0)
            print(f"{cat:32} {tv:>14}  {cv:>14}")
        # 합계
        t_total = sum(t_cat.values())
        c_total = sum(c_cat.values())
        print("-" * 70)
        print(f"{'총 위반':32} {t_total:>14}  {c_total:>14}")
 
    # === 케이스별 위반 내역 (violation_categories 기반) ===
    print("\n" + "=" * 70)
    print("케이스별 위반 내역")
    print("=" * 70)
 
    for label, report in [("함정", report_trap), ("대조군", report_clean)]:
        print(f"\n[{label}]")
        for r in report.get("records", []):
            qid = r["quote_id"]
            rv = r.get("raw_violation")
            fv = r.get("final_violation")
            categories = r.get("violation_categories", []) or []
 
            mark = "❌위반" if rv else ("⚠final위반" if fv else "✅OK")
            print(f"  {qid[:50]:50} {mark}  (위반 {len(categories)}건)")
 
            # 카테고리별 위반 내역 출력
            for v in categories:
                print(f"      - {_fmt_category(v)}")
 
    print(f"\n저장: {out_path}")
 
 
if __name__ == "__main__":
    main()