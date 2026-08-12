from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from fab_identity.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class PageCursor:
    created_at: datetime
    resource_id: UUID

    def encode(self) -> str:
        payload = json.dumps(
            {"created_at": self.created_at.isoformat(), "id": str(self.resource_id)},
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @classmethod
    def decode(cls, value: str | None) -> "PageCursor | None":
        if value is None:
            return None
        try:
            padding = "=" * (-len(value) % 4)
            payload = json.loads(base64.urlsafe_b64decode(value + padding))
            return cls(
                created_at=datetime.fromisoformat(payload["created_at"]),
                resource_id=UUID(payload["id"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValidationError("page cursor is invalid") from exc


def next_cursor(rows: list, limit: int) -> str | None:
    if len(rows) <= limit:
        return None
    boundary = rows[limit - 1]
    return PageCursor(boundary.created_at, boundary.id).encode()
