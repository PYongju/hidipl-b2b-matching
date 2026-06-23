"""
수작 환각 판정용 시트 (v2: 함정/대조군 분리).
- 함정 그룹: trap_dumps/{qid}.json 의 items[:3] 을 보여줌  ← LLM 이 실제로 본 값
- 대조군:    baselines/{qid}.json 의 items[:3] 을 보여줌    ← LLM 이 실제로 본 값
양쪽 다 'LLM 이 본 진실'을 기준으로 LLM 응답과 대조한다.
실행: (backend/app 에서)  python -m tests.trap.manual_audit_sheet
"""
import glob
import json
import os
import sys
 
_DIR = os.path.dirname(__file__)
 
 
# === LLM 응답에서 record-qid → 함정 baseline qid 찾기 (V-02 순위역전 대응) ===
# trap_dumps 가 만들어졌으면 그 안의 items[0].quote_id 를 보면 record-qid 와 매칭 가능
def _build_trap_index() -> dict[str, str]:
    """trap_dumps 의 각 파일을 훑어 'record 에서 보이는 quote_id → 함정 파일명' 매핑."""
    idx: dict[str, str] = {}
    trap_dir = os.path.join(_DIR, "trap_dumps")
    if not os.path.isdir(trap_dir):
        return idx
    for fname in os.listdir(trap_dir):
        if not fname.endswith(".json"):
            continue
        qid_in_file = fname[:-5]  # M-02.json → M-02
        with open(os.path.join(trap_dir, fname), encoding="utf-8") as f:
            d = json.load(f)
        rank1_qid = d["items"][0].get("quote_id") if d.get("items") else None
        if rank1_qid:
            idx[rank1_qid] = qid_in_file
    return idx
 
 
def _fmt_item(it: dict) -> str:
    return (
        f"  quote_id={it.get('quote_id')}\n"
        f"  vendor_name={it.get('vendor_name')!r}\n"
        f"  rank={it.get('rank')}  final_score={it.get('final_score')}\n"
        f"  spec_score={it.get('spec_score')}  price_score={it.get('price_score')}\n"
        f"  delivery_score={it.get('delivery_score')}  warranty_score={it.get('warranty_score')}\n"
        f"  installation_score={it.get('installation_score')}\n"
        f"  warranty_months={it.get('warranty_months')}  delivery_weeks={it.get('delivery_weeks')}\n"
        f"  total_with_vat={it.get('total_with_vat')}\n"
        f"  partner_name={it.get('partner_name')!r}  partner_found={it.get('partner_found')}\n"
        f"  check_required={it.get('check_required')}\n"
        f"  filter_reasons={it.get('filter_reasons')}"
    )
 
 
def main() -> None:
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        files = sorted(glob.glob(os.path.join(_DIR, "reports", "main_run_*.json")))
        if not files:
            print("리포트 없음. 먼저 main_run 실행.")
            return
        path = files[-1]
    print(f"검토 시트 (보고서: {path})\n")
 
    with open(path, encoding="utf-8") as f:
        full = json.load(f)
 
    trap_index = _build_trap_index()
    if not trap_index:
        print("⚠ trap_dumps 가 없습니다. 먼저 'python -m tests.trap.dump_trap_data' 를 실행하세요.\n")
 
    base_dir = os.path.join(_DIR, "baselines")
    trap_dir = os.path.join(_DIR, "trap_dumps")
 
    for group in ["trap", "clean"]:
        print("\n" + "#" * 70)
        print(f"# {group} 그룹  ({'함정 박힌 데이터 기준' if group=='trap' else 'baseline = LLM 입력'})")
        print("#" * 70)
 
        for rec in full[group].get("records", []):
            record_qid = rec["quote_id"]
            print("\n" + "-" * 70)
            print(f"케이스 record-qid: {record_qid}")
            print(f"  raw_violation={rec['raw_violation']}  final_violation={rec['final_violation']}")
 
            # 'LLM 이 본 진실' 데이터 위치 선택
            if group == "trap":
                # record_qid → 함정 파일명 매핑 사용
                trap_qid = trap_index.get(record_qid)
                if not trap_qid:
                    print(f"  ⚠ trap_dumps 에서 record-qid 를 못 찾음 (dump_trap_data 다시 실행 필요)")
                    continue
                src_path = os.path.join(trap_dir, f"{trap_qid}.json")
                print(f"  ※ LLM 입력 출처: trap_dumps/{trap_qid}.json  (함정 박힌 상태)")
            else:
                # 대조군: 그냥 baselines 에서 record_qid 그대로
                src_path = os.path.join(base_dir, f"{record_qid}.json")
                print(f"  ※ LLM 입력 출처: baselines/{record_qid}.json  (정상)")
 
            if not os.path.exists(src_path):
                print(f"  ⚠ 파일 없음: {src_path}")
                continue
 
            with open(src_path, encoding="utf-8") as f:
                d = json.load(f)
 
            print("\nLLM 입력 (items[:3] — 이 값을 진실로 보고 LLM 응답과 대조):")
            for it in d["items"][:3]:
                print(_fmt_item(it))
                print()
 
            print("LLM 응답:")
            raw = rec.get("raw_output") or ""
            try:
                parsed = json.loads(raw)
                print(f"  overall_summary: {parsed.get('overall_summary')!r}\n")
                for s in parsed.get("supplier_explanations", []):
                    print(f"  - quote_id={s.get('quote_id')}  vendor={s.get('vendor_name')}  rank={s.get('rank')}")
                    print(f"    card_summary: {s.get('card_summary')!r}")
                    for k in ("strengths", "weaknesses"):
                        for line in s.get(k, []):
                            print(f"    {k[:1]}: {line}")
                    print()
            except Exception:
                print(raw[:500])
 
    print("\n" + "=" * 70)
    print("수작 검토 가이드")
    print("=" * 70)
    print("""각 케이스마다 'LLM 입력' 과 'LLM 응답' 을 대조:
  [#2] LLM 응답에 입력에 없는 구체 수치(가격/사양/점수)가 나오나? → 위반
  [#3] LLM 입력의 check_required (예: '납기 정보 미기재') 항목이 LLM 응답의 weaknesses 등에 명시됐나? 누락이면 위반
  [#1] LLM 이 점수를 새로 만들어 보고하면? (예: '종합점수 87점' 인데 입력은 81.58) → 위반
 
발견 시: 위반 케이스 / 유형 / 한 줄 인용을 기록.
합격 기준: 위반 0건. 1건이라도 있으면 프롬프트·화이트리스트 재조정 후 재실행.
""")
 
 
if __name__ == "__main__":
    main()