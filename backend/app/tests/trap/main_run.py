

"""
본 실행: 함정 8건 + 대조군 8건 채점.
실행: (backend/app 에서)  python -m tests.trap.main_run
산출: tests/trap/reports/main_run_{timestamp}.json
"""
import datetime
import json
import os
 
from tests.trap.baseline_loader import get_normal_result
from tests.trap.trap_injection_verify import run_injection_check
from tests.trap.llm_violation_eval import evaluate
from services.explanation.explanation_input_builder import build_explanation_input
from services.config import get_settings
 
 
QIDS = ["M-02", "M-10", "M-15", "V-01", "V-02", "V-05", "V-09", "V-15"]
 
 
def main() -> None:
    settings = get_settings()
 
    # === (A) 함정 그룹 ===
    # run_injection_check 가 patched RecommendationPipelineResult 8개의 리스트를 돌려준다.
    print("\n=== (A) 함정 8건 채점 시작 ===")
    trap_dataset, ok = run_injection_check(get_normal_result, build_explanation_input)
    assert ok, "1차 게이트 실패 — baseline/패치 점검 필요"
    report_trap = evaluate(trap_dataset, settings)
    print(f"  함정 그룹 채점 완료. total_llm={report_trap.get('total_llm')}")
 
    # === (B) 대조군 (패치 없이 baseline 그대로) ===
    # evaluate 는 RecommendationPipelineResult 객체의 리스트를 받는다 (dict 아님!).
    # 패치를 안 거치고 get_normal_result 결과를 그대로 넣으면 = 함정 없는 정상 입력.
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
    print("\n" + "=" * 60)
    print("핵심 지표 요약")
    print("=" * 60)
    print(f"{'':28} {'함정':>10}  {'대조군':>10}")
    keys = [
        ("total_llm", "total_llm"),
        ("violation_rate_primary", "위반율(raw, 주지표)"),
        ("violation_rate_final", "위반율(final)"),
        ("postprocess_correction_rate", "후처리 보정율"),
        ("raw_output_missing_count", "raw 누락"),
        ("fallback_rate", "폴백율"),
        ("config_errors", "config_errors"),
    ]
    for k, label in keys:
        tv = report_trap.get(k, "?")
        cv = report_clean.get(k, "?")
        print(f"{label:28} {str(tv):>10}  {str(cv):>10}")
#==== 케이스별 위반 내역==============
    print("\n" + "=" * 60)
    print("케이스별 위반 내역")
    print("=" * 60)

    from tests.trap.llm_violation_eval import BANNED_PHRASES
    def _matched_phrases(raw):
        """raw 응답에서 매칭된 금칙어들을 찾아 돌려준다."""
        if not raw:
            return []
        return [p for p in BANNED_PHRASES if p in raw]
    
    for label, report in [("함정", report_trap), ("대조군", report_clean)]:
        print(f"\n[{label}]")
        for r in report.get("records", []):
            qid = r["quote_id"]
            rv = r["raw_violation"]
            fv = r["final_violation"]
            mark = "❌위반" if rv else ("⚠final위반" if fv else "✅OK")
            print(f"  {qid:50} {mark}   provider={r.get('provider')}")
            if rv or fv:
                raw = (r.get("raw_output") or "")
                hits = _matched_phrases(raw)
                print(f"         매칭된 금칙어: {hits}")
                # 금칙어가 들어있는 문장 주변 80자씩 보여주기
                for phrase in hits:
                    idx = raw.find(phrase)
                    if idx >= 0:
                        start = max(0, idx - 50)
                        end = min(len(raw), idx + 50)
                        snippet = raw[start:end].replace("\n", " ")
                        print(f"         ...«{snippet}»...")
 
    print(f"\n저장: {out_path}")
 
 
if __name__ == "__main__":
    main()