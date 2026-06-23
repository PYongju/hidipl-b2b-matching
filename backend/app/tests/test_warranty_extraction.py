from services.parser.rule_based_quote_parser import RuleBasedQuoteParser


def assert_warranty(text: str, expected: int | None) -> None:
    parser = RuleBasedQuoteParser()
    raw_matches = {}
    actual = parser._extract_warranty_months(text, raw_matches)
    assert actual == expected, (text, expected, actual, raw_matches)
    print(text, "->", actual, raw_matches)


def main() -> None:
    assert_warranty("유지보수 : 설치완료일로부터 2년 무상 (출장실비 별도)", 24)
    assert_warranty("시공후 1년 무상보증, 1년 이후 유상보증", 12)
    assert_warranty("제품무상보증기간 : 준공일로부터 1년", 12)
    assert_warranty("유상 보수 정비 요율 : 별도협의", None)
    assert_warranty("A/S 6개월 무상", 6)
    assert_warranty("무 상 보 수 기 간 : 납품완료 후 12개월", 12)


if __name__ == "__main__":
    main()
