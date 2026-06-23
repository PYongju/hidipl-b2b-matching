from dataclasses import dataclass, field


@dataclass
class EmbeddingResult:
    text: str
    vector: list[float]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class QuoteEmbeddingInput:
    quote_id: str | None
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class RequirementEmbeddingInput:
    requirement_id: str | None
    text: str
    metadata: dict[str, str] = field(default_factory=dict)
