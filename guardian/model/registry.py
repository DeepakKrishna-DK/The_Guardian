"""
Guardian Model Registry
=======================
Discovers, registers, and selects model backends.

Purpose:    Single point of model backend management for all of Guardian.
            Guardian core calls get_model() — it never constructs backends directly.
Inputs:     Optional backend name preference
Outputs:    A ready ModelInterface instance
Deps:       guardian.model.interface + concrete backends
Permissions: Level 0 (read env, no writes)
Failure:    Raises ModelUnavailableError if no backend is available

Selection priority (when no preference given):
  1. GUARDIAN_MODEL_BACKEND env var (explicit user choice)
  2. First available backend in registration order
  3. MockBackend (always available — for testing only)
"""

from __future__ import annotations

import os
from typing import Type

from guardian.logging.logger import get_logger
from guardian.model.interface import (
    BackendInfo,
    ModelInterface,
    ModelUnavailableError,
)

log = get_logger(__name__)

ENV_BACKEND_KEY = "GUARDIAN_MODEL_BACKEND"


class ModelRegistry:
    """
    Registry of model backends.

    Usage:
        registry = ModelRegistry()
        registry.register("mock", MockBackend)
        registry.register("groq", GroqBackend)
        model = registry.get_available()
    """

    def __init__(self) -> None:
        # Ordered dict: name -> backend class
        self._backends: dict[str, Type[ModelInterface]] = {}

    def register(self, name: str, backend_class: Type[ModelInterface]) -> None:
        """Register a backend class under a name."""
        self._backends[name] = backend_class
        log.debug(f"Registered backend: {name} ({backend_class.__name__})")

    def get(self, name: str) -> ModelInterface:
        """
        Instantiate and return a specific backend by name.
        Raises KeyError if name is not registered.
        """
        if name not in self._backends:
            available = list(self._backends.keys())
            raise KeyError(f"Backend {name!r} not registered. Available: {available}")
        return self._backends[name]()

    def get_available(self, prefer: str | None = None) -> ModelInterface:
        """
        Return the best currently available backend.

        Selection order:
          1. `prefer` argument (if given and available)
          2. GUARDIAN_MODEL_BACKEND env var (if set and available)
          3. First registered backend that reports is_available()=True
          4. Raises ModelUnavailableError if nothing is available

        The mock backend is NOT selected automatically unless explicitly
        named or it is the only registered backend.
        """
        env_prefer = os.environ.get(ENV_BACKEND_KEY, "").strip().lower()
        candidates = [prefer, env_prefer if env_prefer else None]

        for name in candidates:
            if name and name in self._backends:
                instance = self._backends[name]()
                if instance.is_available():
                    log.info(f"Using backend: {name} (explicitly selected)")
                    return instance
                else:
                    log.warning(f"Backend {name!r} requested but not available: {instance.get_info().notes}")

        # Auto-select: first non-mock available backend
        for name, cls in self._backends.items():
            if name == "mock":
                continue
            instance = cls()
            if instance.is_available():
                log.info(f"Auto-selected backend: {name}")
                return instance

        # Final fallback: mock (only if it's registered)
        if "mock" in self._backends:
            instance = self._backends["mock"]()
            if instance.is_available():
                log.warning("No real backend available — using MockBackend (test only)")
                return instance

        raise ModelUnavailableError(
            "No model backend is available. "
            "Set GUARDIAN_GROQ_API_KEY or GUARDIAN_GOOGLE_API_KEY, "
            "or install Ollama for local inference."
        )

    def list_all(self) -> list[BackendInfo]:
        """Return BackendInfo for every registered backend."""
        infos = []
        for cls in self._backends.values():
            try:
                infos.append(cls().get_info())
            except Exception as exc:
                log.warning(f"Could not get info for {cls.__name__}: {exc}")
        return infos

    def list_available(self) -> list[BackendInfo]:
        """Return BackendInfo for backends that are currently available."""
        return [info for info in self.list_all() if info.available]


# ---------------------------------------------------------------------------
# Default registry (singleton used by Guardian core)
# ---------------------------------------------------------------------------

def _build_default_registry() -> ModelRegistry:
    """Build the standard Guardian model registry with all known backends."""
    registry = ModelRegistry()

    # Import order = priority order for auto-selection
    try:
        from guardian.model.backends.groq_backend import GroqBackend
        registry.register("groq", GroqBackend)
    except Exception as exc:
        log.warning(f"Could not register Groq backend: {exc}")

    try:
        from guardian.model.backends.gemini_backend import GeminiBackend
        registry.register("gemini", GeminiBackend)
    except Exception as exc:
        log.warning(f"Could not register Gemini backend: {exc}")

    try:
        from guardian.model.backends.ollama_backend import OllamaBackend
        registry.register("ollama", OllamaBackend)
    except Exception as exc:
        log.warning(f"Could not register Ollama backend: {exc}")

    # Mock always last — test use only
    from guardian.model.backends.mock import MockBackend
    registry.register("mock", MockBackend)

    return registry


# Module-level default registry
_default_registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    """Return the module-level default registry (lazy init)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = _build_default_registry()
    return _default_registry


def get_model(prefer: str | None = None) -> ModelInterface:
    """
    Get the best available model backend.
    This is the primary entry point for Guardian components.

    Usage:
        from guardian.model.registry import get_model
        model = get_model()
        response = model.complete(request)
    """
    return get_registry().get_available(prefer=prefer)
