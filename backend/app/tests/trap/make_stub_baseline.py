"""
stub(가짜) baseline 생성기 — 4단계
====================================
진짜 baseline JSON 이 오기 전, '형식만 진짜와 동일한' 가짜 baseline 을 만든다.
값은 가짜지만 필드·타입·quote_id·top3 배치가 진짜와 같으므로,
이걸로 1차 게이트(5단계)를 미리 끝까지 돌려볼 수 있다.

실행:  (backend/app 에서)  python -m tests.trap.make_stub_baseline
산출:  tests/trap/baselines/{quote_id}.json  (8개)

진짜 baseline 이 오면 이 JSON 들을 그대로 교체하면 끝(코드 변경 0).
"""
import json
import os
from dataclasses import asdict

from services.recommendation.schemas import (
    RecommendationItem,
    RecommendationPipelineResult,
)

_DIR = os.path.join(os.path.dirname(__file__), "baselines")

QIDS = ["M-02", "M-10", "M-15", "V-01", "V-02", "V-05", "V-09", "V-15"]


def _normal_item(quote_id: str, rank: int, final_score: float) -> RecommendationItem:
    """함정이 덮어쓸 필드까지 전부 '정상값'으로 채운 아이템(필수 필드 누락 없음)."""
    return RecommendationItem(
        rank=rank,
        quote_id=quote_id,
        partner_name="정상파트너",
        partner_found=True,
        is_premium=False,
        success_rate=0.7,
        response_speed="normal",
        financial_status="normal",
        business_rule_passed=True,
        business_stage="passed",
        filter_reasons=[],
        business_sort_key=[rank],
        vendor_name=f"정상업체_{quote_id}",
        project_name="회의실 디스플레이",
        source_file_path=None,
        final_score=final_score,
        spec_score=80.0,
        price_score=80.0,
        delivery_score=80.0,
        warranty_score=80.0,
        installation_score=80.0,
        cosine_similarity=0.7,
        total_supply_price=12800000,
        total_with_vat=14080000,
        delivery_weeks=8,
        delivery_basis_raw="발주 후 8주",
        warranty_months=24,
        line_item_count=3,
        check_required=[],
        score_breakdown={},
    )


def build_stub_result(qid: str) -> RecommendationPipelineResult:
    """타깃(qid)을 rank 1 에 두고, 정상 아이템 2개를 rank 2·3 으로 채운 top3 결과."""
    items = [
        _normal_item(qid, rank=1, final_score=90.0),          # 타깃 = top3 보장
        _normal_item(f"{qid}-x2", rank=2, final_score=70.0),  # filler (패치 대상 아님)
        _normal_item(f"{qid}-x3", rank=3, final_score=50.0),  # filler
    ]
    return RecommendationPipelineResult(
        request_id=f"stub-{qid}",
        customer_name="스텁고객",
        top_n=3,
        items=items,
        all_items=items,
        failed_candidates=[],
        filtered_candidates=[],
        metadata={},
    )


def main() -> None:
    os.makedirs(_DIR, exist_ok=True)
    for qid in QIDS:
        result = build_stub_result(qid)
        path = os.path.join(_DIR, f"{qid}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2)
        print(f"  wrote {path}")
    print(f"완료: stub baseline {len(QIDS)}개 생성")


if __name__ == "__main__":
    main()
