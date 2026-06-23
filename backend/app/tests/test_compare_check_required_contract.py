from services.explanation.explanation_input_builder import build_explanation_input
from services.explanation.explanation_text_policy import split_comparison_risks
from services.test_explanation_provider import build_recommendation_fixture


def main() -> None:
    checks, risks = split_comparison_risks(
        [
            "납기 별도협의",
            "전기공사 별도",
            "가격 차이 5% 초과 확인 필요",
        ],
        ["최저가 대비 가격 차이 5% 초과"],
    )
    assert checks == ["납기 별도협의", "전기공사 별도"]
    assert risks == ["가격 차이 5% 초과 확인 필요"]

    payload = build_explanation_input(build_recommendation_fixture())
    second = payload.top_items[1]
    assert second["check_required"] == []
    assert second["comparison_risks"] == ["최저가 대비 가격 차이 5% 초과"]
    assert "parser_quality_notes" not in second
    print("compare check_required contract: ok")


if __name__ == "__main__":
    main()
