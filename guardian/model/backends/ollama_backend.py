"""
Ollama Model Backend
====================
Provides local inference via the Ollama HTTP API.
No API keys required. Data never leaves the machine.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from guardian.logging.logger import get_logger
from guardian.model.interface import (
    BackendInfo,
    ModelError,
    ModelInterface,
    ModelRequest,
    ModelResponse,
    ModelUnavailableError,
    TokenUsage,
)

log = get_logger(__name__)


class OllamaBackend(ModelInterface):
    """
    Ollama Backend using the local /api/chat endpoint.
    Expects Ollama to be running on localhost:11434.
    """

    def __init__(self, model_name: str | None = None, model: str | None = None) -> None:
        self.endpoint = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434").rstrip("/")
        self.model_name = model or model_name or os.environ.get("GUARDIAN_OLLAMA_MODEL", "llama3.2:3b")
        self._provider = "Ollama Local"

    def get_info(self) -> BackendInfo:
        return BackendInfo(
            name="ollama",
            provider=self._provider,
            model=self.model_name,
            available=self._check_availability(),
            requires_key=False,
            is_local=True,
            notes="Requires Ollama running locally.",
        )

    def is_available(self) -> bool:
        return self._check_availability()

    def _check_availability(self) -> bool:
        """Ping the Ollama tags endpoint to check if the server is up."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        return False

    def complete(self, request: ModelRequest) -> ModelResponse:
        url = f"{self.endpoint}/api/chat"

        # Prepare messages
        messages = []
        for msg in request.all_messages():
            m_dict = {
                "role": msg.role.value,
                "content": msg.content
            }
            if msg.images:
                m_dict["images"] = msg.images
            messages.append(m_dict)

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            }
        }

        # Merge any backend-specific metadata
        if request.metadata:
            payload.update(request.metadata)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            # First inference can be slow as the model loads into VRAM
            with urllib.request.urlopen(req, timeout=120.0) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ModelUnavailableError(f"Ollama server not reachable at {self.endpoint}: {exc}")
        except Exception as exc:
            raise ModelError(f"Ollama inference failed: {exc}")

        content = result.get("message", {}).get("content", "")

        usage = TokenUsage(
            prompt_tokens=result.get("prompt_eval_count", 0),
            completion_tokens=result.get("eval_count", 0),
            total_tokens=result.get("prompt_eval_count", 0) + result.get("eval_count", 0),
        )

        return ModelResponse(
            content=content,
            model=result.get("model", self.model_name),
            provider=self._provider,
            usage=usage,
            raw=result,
        )
