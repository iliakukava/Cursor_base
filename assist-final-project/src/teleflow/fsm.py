from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PendingForward:
    text: str
    source_link: str | None


class ConversationState:
    def __init__(self) -> None:
        self._pending_by_user: dict[int, PendingForward] = {}

    def set_pending(self, user_id: int, text: str, source_link: str | None) -> None:
        self._pending_by_user[user_id] = PendingForward(text=text, source_link=source_link)

    def get_pending(self, user_id: int) -> PendingForward | None:
        return self._pending_by_user.get(user_id)

    def clear_pending(self, user_id: int) -> None:
        self._pending_by_user.pop(user_id, None)

