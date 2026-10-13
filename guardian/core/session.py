"""
Guardian Session — Working Memory
===================================
Maintains conversation context for a single interaction session.

Constitution reference: Section 8 (Memory) — Working Memory layer.
This is the simplest memory tier: in-process, ephemeral, cleared when
the session ends. No persistence yet (that is Phase 4).

Purpose:    Hold ordered message history for the current conversation
Inputs:     User messages and assistant responses added turn by turn
Outputs:    Ordered list of Messages ready to pass to the model
Deps:       guardian.model.interface
Permissions: Level 0 — in-memory only, no writes to disk
Failure:    History trimmed gracefully if it exceeds the limit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from guardian.model.interface import Message, Role

# Maximum turns kept in active context.
# Older turns are dropped from the front.
# 20 turns = 40 messages (user + assistant each).
MAX_TURNS = 20


@dataclass
class Turn:
    """A single exchange: one user message and one assistant reply."""
    turn_number: int
    user_message: str
    assistant_reply: str
    timestamp: datetime = field(default_factory=datetime.now)
    model_provider: str = ""
    model_name: str = ""
    duration_ms: float = 0.0
    tokens_used: int = 0


class Session:
    """
    Working memory for one Guardian conversation.

    Usage:
        session = Session()
        session.add_turn("hello", "Hi! How can I help?")
        messages = session.to_messages()  # pass to ModelRequest
    """

    def __init__(self, max_turns: int = MAX_TURNS) -> None:
        self._turns: list[Turn] = []
        self._raw_messages: list[Message] = []   # Extra messages from tool loop
        self._max_turns = max_turns
        self.started_at: datetime = datetime.now()

    def add_turn(
        self,
        user_message: str,
        assistant_reply: str,
        model_provider: str = "",
        model_name: str = "",
        duration_ms: float = 0.0,
        tokens_used: int = 0,
    ) -> Turn:
        """Record a completed turn. Trims history if over the limit."""
        turn = Turn(
            turn_number=len(self._turns) + 1,
            user_message=user_message,
            assistant_reply=assistant_reply,
            model_provider=model_provider,
            model_name=model_name,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
        )
        self._turns.append(turn)

        # Trim oldest turns if over limit
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns:]

        return turn

    def add_raw_assistant_message(self, content: str) -> None:
        """
        Inject a raw assistant message into the conversation history.
        Used by the tool loop to insert tool results so the model can
        see them in the next round without creating a fake user/assistant pair.
        These messages are included in to_messages() output.
        """
        self._raw_messages.append(Message(role=Role.ASSISTANT, content=content))

    def to_messages(self) -> list[Message]:
        """
        Flatten session history into an ordered list of Messages.
        Suitable for passing directly to ModelRequest.messages.
        Includes any raw injected messages (e.g., from tool loop).
        """
        messages: list[Message] = []
        for turn in self._turns:
            messages.append(Message(role=Role.USER, content=turn.user_message))
            messages.append(Message(role=Role.ASSISTANT, content=turn.assistant_reply))
        # Append raw messages (tool results) at the end of history
        messages.extend(self._raw_messages)
        return messages

    def to_messages_with_next(self, user_input: str) -> list[Message]:
        """
        Return full history plus the new user input as the final message.
        Use this to build the next ModelRequest.
        """
        messages = self.to_messages()
        messages.append(Message(role=Role.USER, content=user_input))
        return messages

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def next_turn_number(self) -> int:
        return len(self._turns) + 1

    @property
    def total_tokens(self) -> int:
        return sum(t.tokens_used for t in self._turns)

    def clear(self) -> None:
        """Clear conversation history and raw injected messages."""
        self._turns.clear()
        self._raw_messages.clear()

    def last_turn(self) -> Turn | None:
        return self._turns[-1] if self._turns else None

    def summary(self) -> str:
        """One-line summary for display."""
        return (
            f"Session: {self.turn_count} turns, "
            f"{self.total_tokens} tokens used, "
            f"started {self.started_at.strftime('%H:%M:%S')}"
        )
