"""저장된 main_run 리포트에서 어느 함정이 LLM 을 속였는지 본다."""
import glob
import json
import os
import sys

_DIR = os.path.dirname(__file__)


def main() -> None:
    # 인자로 파일 경로 받거나, 없으면 가장 최근 파일 자동 선택
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        files = sorted(glob.glob(os.path.join(_DIR, "reports", "main_run_*.json")))
        path = files[-1]
    print(f"보고서: {path}\n")

    with open(path, encoding="utf-8") as f:
        report = json.load(f)

    for group in ["trap", "clean"]:
        print(f"=== {group} ===")
        records = report[group].get("records") or report[group].get("per_record") or []
        for r in records:
            qid = r.get("quote_id") or r.get("id") or "?"
            v_raw = r.get("is_violation_raw")
            v_final = r.get("is_violation_final")
            print(f"  {qid:6} raw_violation={v_raw}  final_violation={v_final}")
            if v_raw or v_final:
                # 위반이면 raw 텍스트 일부 보기
                raw = r.get("raw_output") or r.get("text") or ""
                if raw:
                    print(f"         raw[:200]: {raw[:200]}")
        print()


if __name__ == "__main__":
    main()

