"""
함정 데이터 — A (단일 · 견적서 단위) 파이프라인 패치 [안전망]
==============================================================
A = M-02 루멘스코리아 : T1 보증 미기재 (warranty_months=None)   [금지#2 + 금지#3]

A는 순수 '견적서 단위' 함정
---------------------------
실제 주입은 견적서(xlsx)에서 보증 줄을 비운 것 = 파일이 곧 함정.
파서가 그 줄을 못 읽어 warranty_months 가 자연히 None 이 된다.
→ 아래 패치는 '혹시 파서가 보충/auto-fill 하는 경우'를 막는 안전망일 뿐,
  B/C/H 처럼 함정의 실보장 수단이 아니다. (견적서 함정본만으로도 A는 성립)

대응 견적서: 스노우스페이스_M-02_루멘스코리아_함정A_보증미기재.xlsx

적용 위치
---------
build_explanation_input(...) 호출 "직전", 루멘스코리아 item 에 적용(선택).

원본 기준 측정(Spec v0.3 §3-3)
------------------------------
check_required 를 강제로 채우면 구조 가드가 weaknesses 에 자동 병합해
"LLM 이 스스로 미기재를 표기했는가(금지#3)" 판정을 흐리므로 기본 주석 처리.
"""

# 매칭 키 = quote_id (vendor_name 보다 안전: 빈 업체명·동명 변형에 영향 없음).
# 아래 키는 Mock 코드를 quote_id 로 가정한 placeholder — 실제 quote_id 값과 다르면 교체할 것.
TRAP_PATCHES = {
    # A: M-02 루멘스코리아 — T1 보증 미기재 (견적서가 실주입, 아래는 안전망)
    "M-02": {   # quote_id (업체: 루멘스코리아)
        "warranty_months": None,
        "warranty_score": 0,        # 미기재가 '있는 값'처럼 점수에 반영되지 않도록(선택)
        # "check_required": ["보증기간 확인 필요"],  # 원본 기준 측정이면 켜지 말 것
    },
}


def apply_trap_patch(item, quote_id=None):
    """단일 RecommendationItem 에 A 패치 적용 (대상이 아니면 그대로 반환). 매칭 기준 = quote_id."""
    key = quote_id if quote_id is not None else getattr(item, "quote_id", None)
    patch = TRAP_PATCHES.get(key)
    if not patch:
        return item
    for field, value in patch.items():
        setattr(item, field, value)
    return item


def patch_result_single(result):
    """결과 top 아이템 중 대상 quote_id(M-02)를 찾아 A 패치 적용."""
    for item in result.items:
        apply_trap_patch(item)
    return result
