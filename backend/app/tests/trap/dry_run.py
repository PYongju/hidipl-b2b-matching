"""
Dry-run: 함정 1건만 채점기에 통과시켜 Azure 호출과 리포트 구조를 확인.
실행: (backend/app 에서)  python -m tests.trap.dry_run
"""
import json

from tests.trap.baseline_loader import get_normal_result
from tests.trap.trap_injection_verify import run_injection_check
from tests.trap.llm_violation_eval import evaluate
from services.explanation.explanation_input_builder import build_explanation_input
from services.config import get_settings


def main() -> None:
    # 1) 1차 게이트 한 번 더 돌려서 eval_dataset 얻기 (PASS 확인 후 진행)
    eval_dataset, ok = run_injection_check(get_normal_result, build_explanation_input)
    assert ok, "1차 게이트 실패 — baseline/패치 점검 필요"

    # 2) 딱 1건만 골라서 채점기에 넣기 (Azure 호출 1회)
    mini = eval_dataset[:1]
    print(f"\n=== Dry-run: {len(mini)}건 채점 시작 ===\n")
    report = evaluate(mini, get_settings())

    # 3) 리포트 보기 좋게 출력
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # 4) 핵심 지표 요약
    print("\n=== 핵심 지표 점검 ===")
    print(f"config_errors: {report.get('config_errors', '?')}   (0이어야 정상)")
    print(f"raw_output_missing_count: {report.get('raw_output_missing_count', '?')}   (0이어야 정상)")
    print(f"violation_rate_primary: {report.get('violation_rate_primary', '?')}")


if __name__ == "__main__":
    main()