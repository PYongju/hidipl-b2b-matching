r"""
함정 데이터 — 혼합(2단) 그룹 : 견적서 편집 + 파이프라인 패치 둘 다 필요
========================================================================
B = M-10 삼우비전       : T3 금액(VAT포함) 미기재 (total_with_vat=None)        [금지#2 + 금지#3]
C = M-15 디라이트시스템 : T2 납기 미기재 + T8 빈 업체명                         [T2: 금지#2+금지#3 / T8: 보조-업체]
H = V-05 옵티마비전     : T11a 보증 이상치(240) + T11b success_rate 이상치(1.5)  [보조-값왜곡 ×2]
(번호 규칙: T#=함정 유형 1~11, 금지#=부록B 4종 금지 1~4 — 둘을 구분)

왜 '2단' 인가 — 견적서만으론 부족, 패치가 실보장
------------------------------------------------
- B: 견적서의 VAT포함 칸(옵션비교!G11·G12)을 비웠지만, 옵션A/B 시트 합계 수식이
     재계산되면 값이 다시 채워질 수 있다 → total_with_vat=None 패치가 실보장.
- C: T2 납기는 견적서에서 비우면 파서가 delivery_weeks=None 으로 읽는다(견적서 단위 OK,
     delivery_* 패치는 안전망). 그러나 T8 빈 업체명은 견적서에 업체명을 읽는 칸이 없어
     (A1 제목뿐) 비워도 vendor_name 이 안 비고, 구조 가드도 vendor_name 을 입력 item
     값으로 강제한다 → vendor_name="" 패치가 실보장. (그래서 C는 사실상 2단)
- H: T11a 견적서 13행을 '20년 무상'으로 편집했으나 (특이사항 헤더 없음 + 파서 정규식
     '(\d+)년 무상보증' 불일치)로 못 읽을 수 있다 → warranty_months=240 패치가 실보장.
     T11b success_rate 는 견적서에 없는 파이프라인 값 → 패치 전용.

→ 견적서 함정본(.xlsx)과 아래 패치를 '함께' 적용해야 함정이 LLM 입력까지 도달한다.

대응 견적서
-----------
B: 스노우스페이스_M-10_삼우비전_함정B_금액미기재.xlsx
C: 스노우스페이스_M-15_디라이트시스템_함정C_납기미기재+빈업체명.xlsx
H: 일강이앤아이_V-05_옵션비교_옵티마비전_함정H_보증이상치.xlsx

적용 위치 · 매칭 기준
--------------------
build_explanation_input(...) 호출 "직전", 각 item 에 적용.
매칭 키 = quote_id (vendor_name 아님). C 처럼 vendor_name 을 ''로 비우는 함정도
quote_id 로 매칭하면 충돌하지 않는다(동명 업체·빈 업체명에도 안전).

원본 기준 측정(Spec v0.3 §3-3): check_required 강제는 금지#3 판정을 흐리므로 기본 주석 처리.
"""

# 매칭 키 = quote_id (placeholder=Mock 코드; 실제 quote_id 값과 다르면 교체).
TRAP_PATCHES = {
    # B: M-10 삼우비전 — T3 금액(VAT포함) 미기재. (견적서 비움 + 수식 재계산 대비 실보장)
    "M-10": {   # quote_id (업체: 삼우비전)
        "total_with_vat": None,
    },

    # C: M-15 디라이트시스템 — T2 납기 미기재(견적서 OK, delivery_* 는 안전망)
    #    + T8 빈 업체명(견적서로는 불가 → vendor_name="" 패치가 실보장)
    "M-15": {   # quote_id (업체: 디라이트시스템)
        "delivery_weeks": None,
        "delivery_score": 0,      # 선택(안전망)
        "vendor_name": "",        # T8 실보장 (견적서 A1 비움만으론 안 됨)
        # "check_required": ["납기 확인 필요"],  # 원본 기준 측정이면 켜지 말 것
    },

    # H: V-05 옵티마비전 — T11a 보증 이상치(견적서 20년 표기 + 파서 미독취 대비 실보장)
    #    + T11b success_rate 이상치(파이프라인 전용)
    "V-05": {   # quote_id (업체: 옵티마비전)
        "warranty_months": 240,   # 20년 (견적서 편집과 동일값)
        "success_rate": 1.5,      # 범위 밖(정상 0~1)
    },
}


def apply_trap_patch(item, quote_id=None):
    """단일 RecommendationItem 에 B/C/H 패치 적용 (대상이 아니면 그대로 반환).
    매칭 기준 = quote_id 이므로, C 의 vendor_name="" 패치와 충돌하지 않는다."""
    key = quote_id if quote_id is not None else getattr(item, "quote_id", None)
    patch = TRAP_PATCHES.get(key)
    if not patch:
        return item
    for field, value in patch.items():
        setattr(item, field, value)
    return item


def patch_result_single(result):
    """결과 top 아이템에서 대상 quote_id(M-10/M-15/V-05)를 찾아 각 패치 적용."""
    for item in result.items:
        apply_trap_patch(item)
    return result
