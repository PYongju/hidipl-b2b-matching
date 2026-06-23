from abc import ABC, abstractmethod

from services.requirement.schemas import ParsedRequirementResult


class RequirementParserProvider(ABC):
    @abstractmethod
    def parse(self, text: str) -> ParsedRequirementResult:
        pass
