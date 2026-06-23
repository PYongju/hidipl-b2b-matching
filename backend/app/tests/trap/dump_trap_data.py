"""
함정 데이터(패치 적용된 RecommendationPipelineResult) 전체를 JSON 파일로 dump.
 
원래 함정은 코드 실행 중 메모리에서만 만들어졌다가 사라진다.
이 스크립트는 trap_injection_verify 와 동일한 방식으로 함정을 박은 뒤,
그 결과를 사람이 읽기 위해 디스크에 떨군다.
 
실행: (backend/app 에서)  python -m tests.trap.dump_trap_data
산출:
  tests/trap/trap_dumps/{qid}.json          # 함정이 박힌 전체 RecommendationPipelineResult
  tests/trap/trap_dumps/_diff_{qid}.txt     # baseline 과의 차이 (어떤 필드가 어떻게 바뀌었나)
"""
import copy
import json
import os
from dataclasses import asdict
 
from tests.trap.baseline_loader import get_normal_result
from tests.trap.trap_injection_verify import (
    SINGLE_PATCH,
    RANK_INVERSION_QID,
    EXPECTED,
)
# 순위역전(V-02) 함정 모듈
from tests.trap import trap_group2_pipeline_patches as trap_group2
 
 
_DIR = os.path.dirname(__file__)
_OUT = os.path.join(_DIR, "trap_dumps")
 
 
def _to_dict(result) -> dict:
    """RecommendationPipelineResult → dict (JSON 직렬화용)."""
    return {
        "request_id": result.request_id,
        "customer_name": result.customer_name,
        "top_n": result.top_n,
        "items": [asdict(it) for it in result.items],
        "all_items": [asdict(it) for it in result.all_items],
        "failed_candidates": result.failed_candidates,
        "filtered_candidates": result.filtered_candidates,
        "metadata": result.metadata,
    }
 
 
def _diff_for(qid: str, baseline_dict: dict, trap_dict: dict) -> str:
    """함정 박은 결과와 baseline 의 차이를 사람이 읽기 좋게 정리."""
    lines = [f"=== {qid} : baseline vs 함정 차이 ===\n"]
    # items 만 비교 (LLM 에 들어가는 부분)
    for idx, (b_it, t_it) in enumerate(zip(baseline_dict["items"], trap_dict["items"])):
        lines.append(f"\n[items[{idx}]] (rank {b_it.get('rank')})")
        all_keys = sorted(set(b_it.keys()) | set(t_it.keys()))
        for k in all_keys:
            bv = b_it.get(k, "<없음>")
            tv = t_it.get(k, "<없음>")
            if bv != tv:
                lines.append(f"  ▶ {k}:")
                lines.append(f"      baseline = {bv!r}")
                lines.append(f"      함정     = {tv!r}")
    return "\n".join(lines) + "\n"
 
 
def main() -> None:
    os.makedirs(_OUT, exist_ok=True)
 
    # 단일 패치 7개 (값-함정)
    for qid in EXPECTED.keys():
        baseline = get_normal_result(qid)               # 원본 (정상)
        trap = copy.deepcopy(baseline)                  # 사본에 함정 박기
        SINGLE_PATCH[qid].patch_result_single(trap)     # 패치 적용
 
        # JSON 으로 떨굼
        baseline_dict = _to_dict(baseline)
        trap_dict = _to_dict(trap)
        out_path = os.path.join(_OUT, f"{qid}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(trap_dict, f, ensure_ascii=False, indent=2)
        # 차이 요약
        diff_path = os.path.join(_OUT, f"_diff_{qid}.txt")
        with open(diff_path, "w", encoding="utf-8") as f:
            f.write(_diff_for(qid, baseline_dict, trap_dict))
        print(f"  wrote {qid}.json  +  _diff_{qid}.txt")
 
    # 순위 역전 (V-02)
    qid = RANK_INVERSION_QID
    baseline = get_normal_result(qid)
    trap = copy.deepcopy(baseline)
    trap_group2.apply_rank_inversion(trap)
 
    baseline_dict = _to_dict(baseline)
    trap_dict = _to_dict(trap)
    with open(os.path.join(_OUT, f"{qid}.json"), "w", encoding="utf-8") as f:
        json.dump(trap_dict, f, ensure_ascii=False, indent=2)
    with open(os.path.join(_OUT, f"_diff_{qid}.txt"), "w", encoding="utf-8") as f:
        f.write(_diff_for(qid, baseline_dict, trap_dict))
    print(f"  wrote {qid}.json  +  _diff_{qid}.txt   (순위 역전)")
 
    print(f"\n완료: 함정 데이터 8개 dump → {_OUT}")
    print("각 폴더에서:")
    print("  *.json        = 패치 적용된 전체 결과 (LLM 에 실제로 들어가는 모양)")
    print("  _diff_*.txt   = baseline 과의 차이만 추린 요약 (어디가 함정인지 한눈에 보기)")
 
 
if __name__ == "__main__":
    main()