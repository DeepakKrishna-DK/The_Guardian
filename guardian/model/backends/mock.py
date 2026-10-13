"""
Guardian Mock Backend
=====================
A deterministic model backend for testing.

Purpose:    Allow Guardian core and tool tests to run without any API key
            or network connection.
Inputs:     ModelRequest
Outputs:    ModelResponse with predictable, inspectable content
Deps:       None (stdlib only)
Permissions: Level 0 — no side effects, no external calls
Failure:    Never raises (by design — it is the fallback for testing)
"""

from __future__ import annotations

from guardian.model.interface import (
    BackendInfo,
    ModelInterface,
    ModelRequest,
    ModelResponse,
    TokenUsage,
)

PROVIDER = "mock"
MODEL_NAME = "guardian-mock-v1"


class MockBackend(ModelInterface):
    """
    Deterministic mock backend.

    Returns structured, predictable responses so that:
      1. Guardian core logic can be tested without API keys
      2. Tests can assert on response shape and content
      3. CI/offline environments work without credentials

    The response content mirrors the last user message with a prefix,
    making it easy to verify that request routing worked correctly.
    """

    def __init__(self, response_prefix: str = "[MOCK]") -> None:
        self._response_prefix = response_prefix
        self._call_count = 0

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Return a deterministic echo response."""
        self._call_count += 1

        last_user_msg = ""
        for msg in reversed(request.messages):
            if msg.role.value == "user":
                last_user_msg = msg.content
                break

        content = (
            f"{self._response_prefix} "
            f"Received: {last_user_msg!r} "
            f"[call #{self._call_count}, "
            f"temp={request.temperature}, "
            f"max_tokens={request.max_tokens}]"
        )

        prompt_tokens = sum(len(m.content.split()) for m in request.all_messages())
        completion_tokens = len(content.split())

        return ModelResponse(
            content=content,
            model=MODEL_NAME,
            provider=PROVIDER,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            raw={"mock": True, "call_count": self._call_count},
        )

    def is_available(self) -> bool:
        """Mock backend is always available."""
        return True

    def get_info(self) -> BackendInfo:
        return BackendInfo(
            name=PROVIDER,
            provider="Guardian Mock",
            model=MODEL_NAME,
            available=True,
            requires_key=False,
            is_local=True,
            notes=f"Deterministic test backend. Calls made: {self._call_count}",
        )

    @property
    def call_count(self) -> int:
        """Number of complete() calls made to this instance."""
        return self._call_count

    def reset(self) -> None:
        """Reset call counter (useful between test cases)."""
        self._call_count = 0
