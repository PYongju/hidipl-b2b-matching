"""
baseline 로더 — 3단계
======================
baselines/{quote_id}.json 을 읽어 RecommendationPipelineResult 로 복원한다.
trap_injection_verify 가 get_normal_result(qid) 로 호출한다.

값(stub/진짜)과 무관하게 '형식'에만 의존하므로, baseline 이 stub→진짜로 바뀌어도
이 파일은 손댈 필요 없다.
"""
import json
import os

from services.recommendation.schemas import (
    RecommendationItem,
    RecommendationPipelineResult,
)

_DIR = os.path.join(os.path.dirname(__file__), "baselines")


def get_normal_result(qid: str) -> RecommendationPipelineResult:
    path = os.path.join(_DIR, f"{qid}.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)

    items = [RecommendationItem(**it) for it in d["items"]]
    all_items = [RecommendationItem(**it) for it in d.get("all_items", d["items"])]
    return RecommendationPipelineResult(
        request_id=d.get("request_id"),
        customer_name=d.get("customer_name"),
        top_n=d.get("top_n", 3),
        items=items,
        all_items=all_items,
        failed_candidates=d.get("failed_candidates", []),
        filtered_candidates=d.get("filtered_candidates", []),
        metadata=d.get("metadata", {}),
    )
