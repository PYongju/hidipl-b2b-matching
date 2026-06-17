"""
받은 진짜 baseline 3개(시나리오 단위)를 평가용 quote_id 8개에 분산 매핑한다.

매핑 규칙 (함정데이터_정리표의 고객 매핑을 따름):
  스노우스페이스(스스): M-02, M-10, M-15  ← snowspace_led 의 rank 1, 2, 3 을 각자의 rank1 자리로
  일강이니(일강) LED  : V-01, V-02, V-09  ← ilgangeeni_led 의 rank 1, 2, 3 을 각자의 rank1 자리로
  일강이니(일강) VW   : V-15, V-05         ← ilgangeeni_videowall 의 rank 1, 2 를 각자의 rank1 자리로

각 평가 qid 의 baseline = (원본 시나리오의 해당 아이템을 rank1 자리로 옮긴) 사본 + quote_id rename.

실행: (backend/app 에서)  python -m tests.trap.make_real_baseline
산출: baselines/{qid}.json  (8개, 기존 stub/이전 baseline 을 덮어씀)
"""
import copy
import json
import os

_DIR = os.path.dirname(__file__)
_SRC_DIR = os.path.join(_DIR, "fixtures", "baselines_source")
_OUT_DIR = os.path.join(_DIR, "baselines")

# 시나리오 → 파일명
_SCENARIO_FILES = {
    "snowspace_led":        "snowspace_led_explanation_baseline_recommendation.json",
    "ilgangeeni_led":       "ilgangeeni_led_explanation_baseline_recommendation.json",
    "ilgangeeni_videowall": "ilgangeeni_videowall_explanation_baseline_recommendation.json",
}

# 평가 qid → (시나리오, 그 시나리오의 어떤 rank 아이템을 가져올지)
_MAPPING = [
    ("M-02", "snowspace_led",        1),
    ("M-10", "snowspace_led",        2),
    ("M-15", "snowspace_led",        3),
    ("V-01", "ilgangeeni_led",       1),
    ("V-02", "ilgangeeni_led",       2),
    ("V-09", "ilgangeeni_led",       3),
    ("V-15", "ilgangeeni_videowall", 1),
    ("V-05", "ilgangeeni_videowall", 2),
]


def _load_scenario(scen: str) -> dict:
    path = os.path.join(_SRC_DIR, _SCENARIO_FILES[scen])
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"소스 baseline 없음:\n  {path}\n"
            "받은 JSON 3개를 tests/trap/fixtures/baselines_source/ 안에 두세요."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_one(qid: str, scen: str, src_rank: int) -> dict:
    """원본 시나리오에서 src_rank 아이템을 rank1 자리로 옮기고 평가 qid 로 rename."""
    clone = copy.deepcopy(_load_scenario(scen))

    items = clone["items"]
    target = items[src_rank - 1]
    original_target_qid = target["quote_id"]

    # 1) 선택된 아이템을 rank1 자리로 옮기고, 나머지는 원래 순서 유지하며 rank2/3 에
    others = [it for i, it in enumerate(items) if i != (src_rank - 1)]
    new_items = [target] + others

    # 2) rank 필드를 새 위치에 맞춰 업데이트 (1, 2, 3)
    for i, it in enumerate(new_items, 1):
        it["rank"] = i

    # 3) rank1 아이템의 quote_id 를 평가용 ID 로 rename
    new_items[0]["quote_id"] = qid
    clone["items"] = new_items

    # 4) all_items 안에 같은 원본 quote_id 가 있으면 같이 rename (정합성 유지)
    for it in clone.get("all_items", []):
        if it.get("quote_id") == original_target_qid:
            it["quote_id"] = qid

    # 5) 추적용 메타데이터
    clone["request_id"] = f"baseline-eval-{qid}"
    meta = clone.setdefault("metadata", {})
    meta["eval_baseline"] = True
    meta["eval_source_scenario"] = scen
    meta["eval_source_rank"] = src_rank
    meta["eval_original_qid"] = original_target_qid

    return clone


def main() -> None:
    os.makedirs(_OUT_DIR, exist_ok=True)
    for qid, scen, src_rank in _MAPPING:
        baseline = _build_one(qid, scen, src_rank)
        out_path = os.path.join(_OUT_DIR, f"{qid}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(baseline, f, ensure_ascii=False, indent=2)
        final_score = baseline["items"][0].get("final_score")
        vendor = baseline["items"][0].get("vendor_name", "?")
        print(
            f"  wrote baselines/{qid}.json   "
            f"(from {scen} rank{src_rank} = {vendor}, final={final_score})"
        )
    print(f"완료: 진짜 baseline {len(_MAPPING)}개 생성 (8개 평가 qid 에 분산 매핑)")


if __name__ == "__main__":
    main()
