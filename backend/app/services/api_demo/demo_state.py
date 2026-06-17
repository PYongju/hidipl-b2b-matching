from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ConfirmedSelection:
    project_id: str
    product_group: str
    selected_quote_ids: list[str]
    confirmed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class DemoConfirmState:
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], ConfirmedSelection] = {}

    def confirm(
        self,
        *,
        project_id: str,
        product_group: str,
        selected_quote_ids: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> ConfirmedSelection:
        key = (project_id, product_group)
        record = ConfirmedSelection(
            project_id=project_id,
            product_group=product_group,
            selected_quote_ids=list(selected_quote_ids),
            metadata=metadata or {},
        )
        self._store[key] = record
        return record

    def get(self, project_id: str, product_group: str) -> ConfirmedSelection | None:
        return self._store.get((project_id, product_group))

    def get_all(self, project_id: str) -> list[ConfirmedSelection]:
        return [
            record
            for (pid, _), record in self._store.items()
            if pid == project_id
        ]

    def delete(self, project_id: str, product_group: str) -> bool:
        key = (project_id, product_group)
        if key in self._store:
            del self._store[key]
            return True
        return False


demo_confirm_state = DemoConfirmState()