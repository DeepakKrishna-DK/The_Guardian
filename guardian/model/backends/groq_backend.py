"""
Guardian Groq Backend
=====================
Model backend using the Groq API (external service).

Purpose:    Fast inference via Groq cloud API
Inputs:     ModelRequest
Outputs:    ModelResponse
Deps:       groq>=0.37 (must be installed in venv)
Permissions: Level 0 for queries; requires GUARDIAN_GROQ_API_KEY env var
Failure:    Raises ModelUnavailableError if key missing or connection fails
            Raises ModelRequestError if API rejects the request

Security:
  - API key loaded from environment only (never hardcoded)
  - Key is never logged or included in ModelResponse
  - External calls only when is_available() is confirmed
"""

from __future__ import annotations

import os
from typing import Any

from guardian.logging.logger import get_logger
from guardian.model.interface import (
    BackendInfo,
    ModelError,
    ModelInterface,
    ModelRequest,
    ModelRequestError,
    ModelResponse,
    ModelUnavailableError,
    TokenUsage,
)

log = get_logger(__name__)

PROVIDER = "groq"
DEFAULT_MODEL = "openai/gpt-oss-120b"
ENV_KEY_NAME = "GUARDIAN_GROQ_API_KEY"


class GroqBackend(ModelInterface):
    """
    Groq API backend.

    Availability requires:
      1. The `groq` Python package is installed
      2. GUARDIAN_GROQ_API_KEY environment variable is set and non-empty

    The backend does NOT validate the key against the API at init time.
    is_available() performs a structural check only (key present + package importable).
    A real API call in complete() may still fail if the key is invalid.
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily initialise the Groq client. Raises ModelUnavailableError if not possible."""
        if self._client is not None:
            return self._client

        api_key = os.environ.get(ENV_KEY_NAME, "").strip()
        if not api_key:
            raise ModelUnavailableError(
                f"Groq API key not found. Set the {ENV_KEY_NAME} environment variable."
            )

        try:
            from groq import Groq  # type: ignore[import]
        except ImportError as exc:
            raise ModelUnavailableError(
                "groq package is not installed in this environment. "
                "Run: pip install groq"
            ) from exc

        self._client = Groq(api_key=api_key)
        return self._client

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Send request to Groq API and return response."""
        client = self._get_client()

        messages = [m.to_dict() for m in request.all_messages()]

        try:
            log.info(f"Groq request: model={self._model} messages={len(messages)} max_tokens={request.max_tokens}")
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
        except Exception as exc:
            exc_name = type(exc).__name__
            msg = str(exc)
            # Distinguish request-level errors from infrastructure errors
            if "invalid_api_key" in msg.lower() or "authentication" in msg.lower():
                raise ModelUnavailableError(f"Groq authentication failed: {msg}") from exc
            if "rate_limit" in msg.lower():
                raise ModelRequestError(f"Groq rate limit exceeded: {msg}") from exc
            raise ModelError(f"Groq API error ({exc_name}): {msg}") from exc

        choice = response.choices[0]
        content = choice.message.content or ""
        
        # Reasoning models (e.g. openai/gpt-oss-*) store thought in .reasoning
        # and may have empty content when max_tokens is too low.
        # Fall back to reasoning field if content is empty.
        if not content and hasattr(choice.message, "reasoning") and choice.message.reasoning:
            content = choice.message.reasoning.strip()

        if not content:
            raise ModelError("Groq returned an empty response content")

        usage = TokenUsage()
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens or 0,
                completion_tokens=response.usage.completion_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
            )

        log.info(f"Groq response: tokens={usage.total_tokens} finish={choice.finish_reason}")

        return ModelResponse(
            content=content,
            model=response.model,
            provider=PROVIDER,
            usage=usage,
            raw={
                "finish_reason": choice.finish_reason,
                "model": response.model,
            },
        )

    def is_available(self) -> bool:
        """
        Return True if:
          1. groq package can be imported
          2. GUARDIAN_GROQ_API_KEY is set and non-empty

        Does NOT make a network call — structural check only.
        """
        api_key = os.environ.get(ENV_KEY_NAME, "").strip()
        if not api_key:
            return False
        try:
            import groq  # type: ignore[import]  # noqa: F401
            return True
        except ImportError:
            return False

    def get_info(self) -> BackendInfo:
        available = self.is_available()
        key_present = bool(os.environ.get(ENV_KEY_NAME, "").strip())
        return BackendInfo(
            name=PROVIDER,
            provider="Groq API",
            model=self._model,
            available=available,
            requires_key=True,
            is_local=False,
            notes=(
                "Ready" if available
                else f"Unavailable — set {ENV_KEY_NAME} environment variable"
                if not key_present
                else "Unavailable — groq package not installed"
            ),
        )
