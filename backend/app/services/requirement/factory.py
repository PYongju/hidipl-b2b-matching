from services.requirement.base import RequirementParserProvider
from services.requirement.rule_based_requirement_parser import (
    RuleBasedRequirementParser,
)


def create_requirement_parser_provider(
    parser_type: str = "rule",
) -> RequirementParserProvider:
    if parser_type == "rule":
        return RuleBasedRequirementParser()

    raise ValueError(f"지원하지 않는 REQUIREMENT_PARSER_PROVIDER입니다: {parser_type}")
