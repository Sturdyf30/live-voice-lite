from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Conversation:
    messages: list[dict[str, str]] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ConversationStore:
    """Small in-memory session store; the browser owns the session identifier."""

    def __init__(self, history_turns: int) -> None:
        self._history_turns = history_turns
        self._sessions: dict[str, Conversation] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def lock(self, session_id: str) -> asyncio.Lock:
        return self._locks[session_id]

    def messages(self, session_id: str) -> list[dict[str, str]]:
        conversation = self._sessions.setdefault(session_id, Conversation())
        return list(conversation.messages)

    def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        conversation = self._sessions.setdefault(session_id, Conversation())
        conversation.messages.extend(
            [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": assistant_text},
            ]
        )
        max_messages = self._history_turns * 2
        conversation.messages = conversation.messages[-max_messages:]
        conversation.updated_at = datetime.now(UTC)

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._locks.pop(session_id, None)
