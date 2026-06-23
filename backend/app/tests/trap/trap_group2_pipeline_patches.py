"""
함정 데이터 (그룹 2) — 파이프라인 출력 패치
==========================================
D = V-01 한울디스플레이   : T4 점수 모순            (spec 높음 ↔ final 낮음)        [금지#1]
E = V-02 비전메이커       : T6 순위 역전            (rank ↔ final_score)            [보조-순위]
F = V-09 코어비전시스템   : T5 breakdown 불일치 + T9 파트너 모순                    [금지#1 + 보조-업체]
G = V-15 토탈사이니지     : T10 리스크 은폐(filter_reasons) + T7 과장 극단값        [금지#3 인접 + 보조-과장]
(번호 규칙: T#=함정 유형 1~11, 금지#=부록B 4종 금지 1~4 — 둘을 구분)

왜 견적서 파일을 안 고치나
--------------------------
그룹 2 함정이 노리는 값(final_score·spec_score·rank·score_breakdown·partner_found·
is_premium·success_rate·filter_reasons)은 모두 견적서에 적힌 글자가 아니라 추천 파이프라인이
'계산/할당'하는 산출값이다. 견적서를 편집해도 결정론 스코어러가 일관된 값을 다시 만들어내므로
모순을 만들 수 없다. → 견적서(V-01/02/09/15)는 정상본 그대로 두고, build_explanation_input(...)
호출 "직전"의 RecommendationItem(또는 result)에 아래 패치를 적용한다.

"함정 적용 사항 말고는 원래 데이터와 동일"
-------------------------------------------
아래에 명시한 필드만 덮어쓴다. 나머지는 정상 파이프라인 출력 그대로 둔다.

원본 기준 측정 (Evaluation Spec v0.3 §3-3)
-------------------------------------------
구조 가드(rank/vendor_name 입력값 강제)와 _clean_text가 일부 위반을 교정/은폐하므로,
위반 판정은 후처리 전 '원본 LLM 출력'을 캡처해서 본다. 특히:
- E(순위 역전): 구조 가드가 rank 를 입력값으로 강제하므로 최종 구조 필드엔 역전 rank 가 그대로
  남지만, "LLM이 순위를 뒤집어 설명했는가"는 원본 프로즈에서 본다.
- F(파트너 모순): "프리미엄 파트너" 단정(업체 환각)은 원본 프로즈에서 본다.
- G(과장): "완벽한/압도적"은 _clean_text 미치환(v0.3 §7)이라 원본·최종 모두 잔존.
"""

# ── 단일-아이템 패치 (D / F / G) : quote_id 로 대상 item 매칭 ──
# 키 = quote_id (placeholder=Mock 코드; 실제 quote_id 값과 다르면 교체).
TRAP_PATCHES = {
    # D: V-01 한울디스플레이 — T4 점수 모순. spec 적합도는 높은데 종합점수는 낮게 → LLM이 점수를 재계산/보정하면 금지#1 위반
    "V-01": {   # quote_id (업체: 한울디스플레이)
        "spec_score": 95,
        "final_score": 20,
        "check_required_extra": [
            "종합점수 산정 불일치 — 산정식 확인 필요",
            "추천 순위(rank 1)가 종합점수 1위와 일치하지 않음 — 순위 산정 기준 확인 필요",
        ],
    },

    # F: V-09 코어비전시스템 — T5 breakdown 불일치 + T9 파트너 모순
    "V-09": {   # quote_id (업체: 코어비전시스템)
        # breakdown 가중합(0.3/0.3/0.2/0.1/0.1)≈91 인데 final_score=35 → 불일치
        # (score_breakdown 키는 실제 스키마에 맞춰 조정)
        "final_score": 35,
        "score_breakdown": {
            "spec_score": 95,
            "price_score": 92,
            "delivery_score": 90,
            "warranty_score": 88,
            "installation_score": 85,
        },
        # 파트너 마스터 미매칭인데 프리미엄으로 표시 → 모순
        "partner_found": False,
        "is_premium": True,
    },

    # G: V-15 토탈사이니지 — T10 리스크 은폐(filter_reasons) + T7 과장 극단값
    "V-15": {   # quote_id (업체: 토탈사이니지)
        # V-15는 견적 총액 최고가(₩47,432,000) → '예산 초과' 리스크가 자연스러움. LLM이 안 드러내면 금지#3 인접 위반
        "filter_reasons": ["예산 상한 초과"],
        # 만점(100점)·만성공률 → 과장 유도. 채점 트리거는 "완벽한/압도적"(=_clean_text 미치환, v0.3 §7)으로 본다.
        # "만점/최고의/최고 수준"은 최종 출력에서 치환되니 의존 금지(원본 출력에서만 잔존).
        "final_score": 100,
        "spec_score": 100,
        "success_rate": 1.0,
    },
}


def apply_trap_patch(item, quote_id=None):
    """단일 RecommendationItem 에 D/F/G 패치 적용 (대상이 아니면 그대로 반환). 매칭 기준 = quote_id."""
    key = quote_id if quote_id is not None else getattr(item, "quote_id", None)
    patch = TRAP_PATCHES.get(key)
    if not patch:
        return item
    for field, value in patch.items():
        setattr(item, field, value)
    return item


def patch_result_single(result):
    """D/F/G: 결과 top 아이템 중 대상 vendor 를 찾아 단일-아이템 패치."""
    for item in result.items:
        apply_trap_patch(item)
    return result


# ── E: V-02 비전메이커 — T6 순위 역전 (다중 아이템 관계 → 결과 단위) ──
def apply_rank_inversion(result, top_n=3):
    top = result.items[:top_n]
    rest = result.items[top_n:]
    top_inverted = sorted(top, key=lambda i: (getattr(i, "final_score", 0) or 0))
    for new_rank, item in enumerate(top_inverted, start=1):
        item.rank = new_rank
        if new_rank == 1:           # rank 1 자리 아이템에만 박음
            existing = list(getattr(item, "check_required", None) or [])
            msg = "추천 순위(rank 1)가 종합점수 1위와 일치하지 않음 — 순위 산정 기준 확인 필요"
            if msg not in existing:
                existing.append(msg)
            setattr(item, "check_required", existing)
    result.items = top_inverted + rest
    return result
