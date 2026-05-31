from services.parser.base import ParserProvider
from services.parser.rule_based_quote_parser import RuleBasedQuoteParser


def create_parser_provider(parser_type: str = "rule") -> ParserProvider:
    if parser_type == "rule":
        return RuleBasedQuoteParser()

    raise ValueError(f"지원하지 않는 PARSER_PROVIDER입니다: {parser_type}")
