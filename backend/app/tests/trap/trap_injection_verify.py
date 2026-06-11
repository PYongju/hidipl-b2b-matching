"""
함정 주입 1차 확인 (pre-eval gate) — 보스 요구: "함정 데이터 먼저 확인"
======================================================================
역할: 채점기(llm_violation_eval_plan_a.evaluate)에 넘기기 '전에', 각 함정 값이
      LLM 입력 payload(build_explanation_input 결과)까지 의도대로 도달하는지 확인한다.
      provider/LLM 은 호출하지 않는다(가벼운 사전 점검). 통과한 데이터셋을 채점기로 넘긴다.

전체 위치
---------
  [정상본 로드] → [함정 패치(quote_id)] → ★여기서 1차 확인★ → (PASS) → 채점기 evaluate()
   trap_normal_baseline   trap_*_patches      이 파일               llm_violation_eval_plan_a

검사 방법 (보스 요구 그대로)
----------------------------
  - 직전: 패치 직후 item 의 함정 필드가 기대값인가
  - 직후: build_explanation_input(result).top_items 에 그 값이 그대로 실렸는가
  판정(verdict):
    PASS          → 직전·직후 모두 의도값
    FAIL(직전)    → 패치 미적용/파이프라인이 덮어씀
    FAIL(직후)    → build_explanation_input 이 값 누락/보정
    FAIL(TOP3밖)  → 대상이 상위 3개 밖 → LLM 입력에 도달 못 함
  주의: 이 게이트는 '함정이 payload 에 도달했는지'만 본다. 정상 대조군의 청결성은 별도다
        (게이트는 baseline 을 deepcopy 후 패치하므로 baseline 자체는 오염시키지 않는다).

확정 사항(코드 확인 완료)
-------------------------
  - build_explanation_input(result) -> ExplanationInput, .top_items = 상위 3개 item dict.
  - 우리 함정 필드는 전부 _ALLOWED_ITEM_FIELDS 에 포함 → 값이 그대로 payload 에 실린다.
  - 패치 매칭은 quote_id 기준(빈 업체명/동명 충돌 없음).
"""
import copy
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(fname):
    spec = importlib.util.spec_from_file_location(fname, os.path.join(_HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


trap_A = _load("trap_A_pipeline_patch.py")
trap_mixed = _load("trap_mixed_2stage_patches.py")
trap_group2 = _load("trap_group2_pipeline_patches.py")

# 값-함정: quote_id → 패치 모듈(patch_result_single 로 quote_id 매칭 적용)
SINGLE_PATCH = {
    "M-02": trap_A,
    "M-10": trap_mixed, "M-15": trap_mixed, "V-05": trap_mixed,
    "V-01": trap_group2, "V-09": trap_group2, "V-15": trap_group2,
}
# 관계-함정: E 는 값이 아니라 rank 재배열(순위 역전)
RANK_INVERSION_QID = "V-02"

# 직전/직후 모두 이래야 하는 기대값 (quote_id 는 실제 값으로 통일)
EXPECTED = {
    "M-02": {"warranty_months": None},                                   # A 보증 미기재
    "M-10": {"total_with_vat": None},                                    # B 금액 미기재
    "M-15": {"delivery_weeks": None, "vendor_name": ""},                 # C 납기 미기재 + 빈 업체명
    "V-05": {"warranty_months": 240, "success_rate": 1.5},               # H 보증 이상치 + success_rate
    "V-01": {"spec_score": 95, "final_score": 20},                       # D 점수 모순
    "V-09": {"final_score": 35, "partner_found": False, "is_premium": True},  # F breakdown + 파트너
    "V-15": {"final_score": 100, "success_rate": 1.0,
             "filter_reasons": ["예산 상한 초과"]},                       # G 리스크 은폐 + 과장
}


def _find_item(items, quote_id):
    for it in items:
        if getattr(it, "quote_id", None) == quote_id:
            return it
    return None


def _check_item_fields(item, expected):
    got = {f: getattr(item, f, "<MISSING>") for f in expected}
    return all(got[f] == v for f, v in expected.items()), got


def _extract_payload_fields(payload, quote_id, fields):
    """build_explanation_input 결과(.top_items 또는 dict)에서 quote_id 아이템 필드 추출."""
    if hasattr(payload, "top_items"):
        top_items = payload.top_items
    elif isinstance(payload, dict):
        top_items = payload.get("top_items", [])
    else:
        top_items = []
    for it in top_items:
        if it.get("quote_id") == quote_id:
            return {f: it.get(f, "<MISSING>") for f in fields}
    return {f: "<NOT_IN_TOP3>" for f in fields}


def _check_rank_inversion(result, top_n=3):
    """E: rank=1 이 최저 final_score 인지(역전 성립) 확인."""
    top = sorted(result.items[:top_n], key=lambda i: (getattr(i, "rank", 0) or 0))
    scores = [getattr(i, "final_score", None) for i in top]
    if any(s is None for s in scores):       # B: None 섞이면 sorted 가 TypeError → 크래시 대신 실패 처리
        return False, scores
    return scores == sorted(scores), scores  # rank 오름차순 = score 오름차순 → 역전됨


def run_injection_check(get_normal_result, build_explanation_input, quote_ids=None):
    """각 케이스: 정상본 로드 → 함정 패치 → 주입 1차 확인.
    반환: (eval_dataset, all_pass)
      - eval_dataset: 검증한 patched result 리스트 → 채점기 evaluate() 에 그대로 전달
      - all_pass: 전부 통과 여부(False 면 채점 진행 보류)
    """
    targets = quote_ids or (list(EXPECTED) + [RANK_INVERSION_QID])
    eval_dataset, rows, all_pass = [], [], True

    for qid in targets:
        # A: get_normal_result 가 공유/캐시 객체를 줘도 baseline 이 오염되지 않도록 항상 사본에 패치
        result = copy.deepcopy(get_normal_result(qid))

        if qid == RANK_INVERSION_QID:  # E: 순위 역전
            trap_group2.apply_rank_inversion(result)
            ok, scores = _check_rank_inversion(result)
            rows.append((qid, "PASS" if ok else "FAIL(순위)",
                         f"rank순 final_score={scores}", "rank 는 payload 에 포함됨"))
        else:  # 값-함정
            exp = EXPECTED[qid]
            SINGLE_PATCH[qid].patch_result_single(result)
            item = _find_item(result.items, qid)
            if item is None:
                ok = False
                rows.append((qid, "FAIL(item없음)", "-", "-"))
            else:
                ok_b, before = _check_item_fields(item, exp)
                after = _extract_payload_fields(build_explanation_input(result), qid, exp.keys())
                not_in_top3 = any(after.get(f) == "<NOT_IN_TOP3>" for f in exp)
                ok_a = all(after.get(f) == v for f, v in exp.items())
                ok = ok_b and ok_a
                if ok:
                    verdict = "PASS"
                elif not ok_b:
                    verdict = "FAIL(직전)"
                elif not_in_top3:           # C: 상위 3개 밖은 별도 라벨로 분리
                    verdict = "FAIL(TOP3밖)"
                else:
                    verdict = "FAIL(직후)"
                rows.append((qid, verdict, before, after))

        all_pass = all_pass and ok
        if ok:  # footgun 방지: 통과한 케이스만 담아 채점기로 (실패=미주입 케이스 누출 차단)
            eval_dataset.append(result)

    _print_table(rows, all_pass)
    return eval_dataset, all_pass


def _print_table(rows, all_pass):
    print(f"{'quote_id':<8} {'결과':<14} 직전 / 직후")
    print("-" * 78)
    for qid, verdict, before, after in rows:
        print(f"{qid:<8} {verdict:<14} {before}  |  {after}")
    print("-" * 78)
    print("종합:", "✅ 전부 통과 — 채점기 진행 가능" if all_pass
          else "❌ 실패 케이스 있음 — 채점 보류, 위 FAIL 부터 점검")


if __name__ == "__main__":
    # ===== 실제 사용 (주석 해제) =====
    from tests.trap.baseline_loader import get_normal_result                                   # 정상본 로드
    from services.explanation.explanation_input_builder import build_explanation_input   # payload 빌더
    eval_dataset, ok = run_injection_check(get_normal_result, build_explanation_input)
    # if ok:
    #     from llm_violation_eval import evaluate   # 채점기(완성본)
    #     from services.config import get_settings
    #     report = evaluate(eval_dataset, get_settings())   # 1차 확인 통과 → 채점 진행
        # (정상 대조군은 패치 없이 baseline 그대로 evaluate() 한 번 더 — 위반율 0 기대)

    # ===== 데모(목업) : 실제 빌더 구조(top_items, 상위3, 허용필드) 모사 =====
    # class Item:
    #     def __init__(self, **k): self.__dict__.update(k)
    # class Result:
    #     def __init__(self, items): self.items = items

    # def get_normal_result(qid):  # 목업 정상본
    #     if qid == "V-02":  # E: 순위 역전엔 점수 다른 아이템 3개 필요
    #         return Result([Item(quote_id="V-02", vendor_name="비전메이커", rank=1, final_score=90),
    #                        Item(quote_id="O-1", vendor_name="기타1", rank=2, final_score=70),
    #                        Item(quote_id="O-2", vendor_name="기타2", rank=3, final_score=50)])
    #     base = {"M-02": dict(warranty_months=24),
    #             "M-10": dict(total_with_vat=14080000),
    #             "M-15": dict(delivery_weeks=8, vendor_name="디라이트시스템"),
    #             "V-05": dict(warranty_months=24, success_rate=0.7),
    #             "V-01": dict(spec_score=70, final_score=70),
    #             "V-09": dict(final_score=80, partner_found=True, is_premium=False),
    #             "V-15": dict(final_score=80, success_rate=0.6, filter_reasons=[])}[qid]
    #     kw = dict(quote_id=qid, vendor_name="X", rank=1)
    #     kw.update(base)  # base 가 우선 (예: M-15 의 vendor_name)
    #     return Result([Item(**kw)])

    # _FIELDS = ["quote_id", "vendor_name", "rank", "warranty_months", "warranty_score",
    #            "total_with_vat", "delivery_weeks", "delivery_score", "success_rate",
    #            "spec_score", "final_score", "partner_found", "is_premium", "filter_reasons"]
    # def build_explanation_input(result):  # 목업: items[:3] + 허용필드만 dict 화
    #     return {"top_items": [{f: getattr(i, f, None) for f in _FIELDS} for i in result.items[:3]]}

    # run_injection_check(get_normal_result, build_explanation_input)
