"""
Guardian Gemini Backend
=======================
Model backend using the Google Gemini API (google-genai SDK).

Purpose:    Inference via Google Gemini cloud API
Inputs:     ModelRequest
Outputs:    ModelResponse
Deps:       google-genai>=2.8 (must be installed in venv)
Permissions: Level 0 for queries; requires GUARDIAN_GOOGLE_API_KEY env var
Failure:    Raises ModelUnavailableError if key missing or package absent
            Raises ModelRequestError if API rejects the request

Security:
  - API key loaded from environment only (never hardcoded)
  - Key is never logged or included in ModelResponse
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

PROVIDER = "gemini"
DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-3.8-flash"
ENV_KEY_NAME = "GUARDIAN_GOOGLE_API_KEY"


class GeminiBackend(ModelInterface):
    """
    Google Gemini API backend using the google-genai SDK.

    Availability requires:
      1. google-genai package is installed
      2. GUARDIAN_GOOGLE_API_KEY environment variable is set and non-empty
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily initialise the Gemini client."""
        if self._client is not None:
            return self._client

        api_key = os.environ.get(ENV_KEY_NAME, "").strip()
        if not api_key:
            raise ModelUnavailableError(
                f"Gemini API key not found. Set the {ENV_KEY_NAME} environment variable."
            )

        try:
            from google import genai  # type: ignore[import]
        except ImportError as exc:
            raise ModelUnavailableError(
                "google-genai package is not installed. Run: pip install google-genai"
            ) from exc

        self._client = genai.Client(api_key=api_key)
        return self._client

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Send request to Gemini API and return response. Retries with fallback on 503."""
        return self._do_complete(request, model=self._model)

    def _do_complete(self, request: ModelRequest, model: str) -> ModelResponse:
        """Internal completion with explicit model name."""
        client = self._get_client()

        # Build contents list for Gemini API
        # Gemini uses role="user"/"model" (not "assistant")
        # System prompt is passed separately via system_instruction
        contents = []
        for msg in request.messages:
            role = "model" if msg.role.value == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        config: dict[str, Any] = {
            "max_output_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            config["system_instruction"] = request.system_prompt

        try:
            log.info(f"Gemini request: model={model} turns={len(contents)} max_tokens={request.max_tokens}")

            from google.genai import types  # type: ignore[import]
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(**config),
            )
        except Exception as exc:
            exc_name = type(exc).__name__
            msg_str = str(exc)
            if "api_key" in msg_str.lower() or "permission" in msg_str.lower() or "401" in msg_str:
                raise ModelUnavailableError(f"Gemini authentication failed: {msg_str}") from exc
            if "quota" in msg_str.lower() or "429" in msg_str:
                raise ModelRequestError(f"Gemini quota exceeded: {msg_str}") from exc
            # 503 overloaded — try fallback model once
            if ("503" in msg_str or "UNAVAILABLE" in msg_str or "overloaded" in msg_str.lower()) and model != FALLBACK_MODEL:
                log.warning(f"Gemini model {model!r} overloaded (503), retrying with {FALLBACK_MODEL!r}...")
                return self._do_complete(request, model=FALLBACK_MODEL)
            raise ModelError(f"Gemini API error ({exc_name}): {msg_str}") from exc

        content = response.text or ""
        if not content:
            raise ModelError("Gemini returned an empty response")

        usage = TokenUsage()
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = TokenUsage(
                prompt_tokens=getattr(um, "prompt_token_count", 0) or 0,
                completion_tokens=getattr(um, "candidates_token_count", 0) or 0,
                total_tokens=getattr(um, "total_token_count", 0) or 0,
            )

        log.info(f"Gemini response received: tokens={usage.total_tokens}")

        return ModelResponse(
            content=content,
            model=self._model,
            provider=PROVIDER,
            usage=usage,
            raw={"model": self._model},
        )

    def is_available(self) -> bool:
        """Return True if google-genai is importable and API key is set."""
        api_key = os.environ.get(ENV_KEY_NAME, "").strip()
        if not api_key:
            return False
        try:
            from google import genai  # type: ignore[import]  # noqa: F401
            return True
        except ImportError:
            return False

    def get_info(self) -> BackendInfo:
        available = self.is_available()
        key_present = bool(os.environ.get(ENV_KEY_NAME, "").strip())
        return BackendInfo(
            name=PROVIDER,
            provider="Google Gemini API",
            model=self._model,
            available=available,
            requires_key=True,
            is_local=False,
            notes=(
                "Ready" if available
                else f"Unavailable — set {ENV_KEY_NAME} environment variable"
                if not key_present
                else "Unavailable — google-genai package not installed"
            ),
        )
