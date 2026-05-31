from dataclasses import dataclass, field


@dataclass
class SimilarityResult:
    score: float
    method: str
    metadata: dict[str, str] = field(default_factory=dict)
