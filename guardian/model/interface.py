"""
Guardian Model Interface
========================
The single abstraction layer between Guardian and any AI model.

ALL model access in Guardian goes through this interface.
No component may call a model API directly.

Design principles:
  - Model-agnostic: local, API, or future models all use the same interface
  - Replaceable: swap backends without touching Guardian core
  - Honest: backends report availability accurately; no silent failures
  - Minimal: only what is needed now, extensible later

Inputs:   ModelRequest  (messages, system prompt, parameters)
Outputs:  ModelResponse (content, metadata, usage)
Failure:  ModelError    (raised on failure, never silently swallowed)

Permission level: Level 0 for read/query, Level 1 for stateful session
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Message roles
# ---------------------------------------------------------------------------

class Role(str, Enum):
    SYSTEM    = "system"
    USER      = "user"
    ASSISTANT = "assistant"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A single message in a conversation."""
    role: Role
    content: str
    images: list[str] | None = None

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str, images: list[str] | None = None) -> "Message":
        return cls(role=Role.USER, content=content, images=images)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        return cls(role=Role.ASSISTANT, content=content)

    def to_dict(self) -> dict[str, Any]:
        d = {"role": self.role.value, "content": self.content}
        if self.images:
            d["images"] = self.images
        return d


@dataclass
class ModelRequest:
    """
    A request to a model.

    Fields:
        messages:       Ordered conversation history (required)
        system_prompt:  Optional system instruction prepended to messages
        max_tokens:     Maximum tokens to generate (default: 1024)
        temperature:    Sampling temperature 0.0-2.0 (default: 0.7)
        metadata:       Optional pass-through dict for backend-specific options
    """
    messages: list[Message]
    system_prompt: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("ModelRequest requires at least one message")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f"temperature must be 0.0-2.0, got {self.temperature}")
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {self.max_tokens}")

    def all_messages(self) -> list[Message]:
        """Return system prompt (if any) prepended to conversation messages."""
        if self.system_prompt:
            return [Message.system(self.system_prompt)] + self.messages
        return list(self.messages)


@dataclass
class TokenUsage:
    """Token consumption reported by the model backend."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ModelResponse:
    """
    A response from a model backend.

    Fields:
        content:    The model's text output (always present on success)
        model:      Model identifier as reported by the backend
        provider:   Backend name (e.g. "groq", "gemini", "mock")
        usage:      Token usage if reported by the backend
        raw:        Raw response dict from backend (for debugging)
    """
    content: str
    model: str
    provider: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.content)


@dataclass
class BackendInfo:
    """
    Metadata about a model backend.

    Fields:
        name:           Short identifier (e.g. "groq")
        provider:       Human-readable name (e.g. "Groq API")
        model:          Default model name this backend uses
        available:      Whether the backend can currently serve requests
        requires_key:   Whether an API key is needed
        is_local:       Whether inference runs locally (no external calls)
        notes:          Any relevant status notes
    """
    name: str
    provider: str
    model: str
    available: bool
    requires_key: bool
    is_local: bool
    notes: str = ""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ModelError(Exception):
    """Raised when a model backend fails to produce a response."""

class ModelUnavailableError(ModelError):
    """Raised when the backend is not available (no key, no connection, etc.)."""

class ModelRequestError(ModelError):
    """Raised when the request itself is invalid or rejected by the backend."""


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class ModelInterface(ABC):
    """
    Abstract base class for all Guardian model backends.

    Every backend MUST implement:
        complete()     - Send a request, return a response
        is_available() - Return True only if actually usable right now
        get_info()     - Return BackendInfo describing this backend

    Backends MUST NOT:
        - Silently return empty content on failure
        - Claim is_available()=True without verifying
        - Store or log message content without explicit permission
    """

    @abstractmethod
    def complete(self, request: ModelRequest) -> ModelResponse:
        """
        Send a request to the model and return its response.

        Raises:
            ModelUnavailableError  if the backend is not available
            ModelRequestError      if the request was rejected
            ModelError             for any other failure
        """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True if this backend can currently serve requests.
        Must perform an actual availability check, not just return a cached flag.
        """

    @abstractmethod
    def get_info(self) -> BackendInfo:
        """Return metadata about this backend."""

    def __repr__(self) -> str:
        info = self.get_info()
        status = "available" if info.available else "unavailable"
        return f"<{self.__class__.__name__} provider={info.provider!r} model={info.model!r} {status}>"

    @property
    def locality(self) -> str:
        """Return 'local' or 'cloud' based on whether inference runs locally."""
        try:
            return "local" if self.get_info().is_local else "cloud"
        except Exception:
            return "cloud"  # fail closed
