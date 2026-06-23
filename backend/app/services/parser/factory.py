import os

from services.parser.base import ParserProvider
from services.parser.llm_quote_parser import LLMQuoteParserProvider
from services.parser.rule_based_quote_parser import RuleBasedQuoteParser


def create_parser_provider(
    parser_type: str | None = None,
    *,
    settings=None,
) -> ParserProvider:
    selected = (parser_type or os.getenv("QUOTE_PARSER_PROVIDER") or "rule").lower()

    if selected == "rule":
        return RuleBasedQuoteParser()

    if selected == "llm":
        return LLMQuoteParserProvider(settings=settings)

    if selected == "llm_with_rule_fallback":
        return LLMQuoteParserProvider(
            settings=settings,
            fallback_provider=RuleBasedQuoteParser(),
        )

    raise ValueError(f"Unsupported QUOTE_PARSER_PROVIDER: {selected}")
