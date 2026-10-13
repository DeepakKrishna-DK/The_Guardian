"""
guardian.model.router
=====================
Routes requests to different backends based on:
  - call_type (PLANNING / SYNTHESIS / CRITIQUE / ROUTINE)
  - require_local flag  → hard deny + audit event if no local backend available

Constitution compliance:
  § 2.2 Privacy by Default  — local-only requests NEVER fall back to cloud.
  Any hard-deny is recorded in the audit log as "model.local_only_denied".
"""
from __future__ import annotations

from enum import Enum
from guardian.model.interface import ModelInterface, ModelUnavailableError
from guardian.model.registry import get_registry


class CallType(Enum):
    PLANNING = "planning"
    SYNTHESIS = "synthesis"
    CRITIQUE = "critique"
    ROUTINE = "routine"


class ModelRouter:
    """
    Routes requests to different models based on call type and data-locality requirements.
    
    Hard invariant (constitution §2.2):
      require_local=True → must return a local backend or raise ModelUnavailableError.
      It NEVER silently falls back to a cloud backend.  Any denial is audited.
    """

    def __init__(
        self,
        primary: ModelInterface,
        cheap: ModelInterface | None = None,
        local: ModelInterface | None = None,
    ) -> None:
        self.primary = primary
        self.cheap = cheap or primary
        self.local = local

    def route(self, call_type: CallType, require_local: bool = False) -> ModelInterface:
        """Return the appropriate backend.  Raises ModelUnavailableError on hard-deny."""
        if require_local:
            candidate = self._pick_local()
            if candidate is not None:
                return candidate
            # Hard deny — write audit event before raising
            self._audit_local_denied(call_type)
            raise ModelUnavailableError(
                "Constitution §2.2 hard deny: this operation requires a local model to "
                "preserve privacy, but no local backend is available.  "
                "Start Ollama (`ollama serve`) or configure a local backend."
            )

        if call_type in (CallType.PLANNING, CallType.ROUTINE):
            return self.cheap
        return self.primary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pick_local(self) -> ModelInterface | None:
        """Return the first available truly-local backend, or None."""
        for candidate in (self.local, self.primary, self.cheap):
            if candidate is not None:
                try:
                    if candidate.get_info().is_local:
                        return candidate
                except Exception:
                    pass
        return None

    @staticmethod
    def _audit_local_denied(call_type: CallType) -> None:
        """Record a model.local_only_denied event in the audit log."""
        try:
            from guardian.audit import get_audit_log
            get_audit_log().append(
                "model.local_only_denied",
                payload={
                    "call_type": call_type.value,
                    "reason": "no local backend available",
                    "constitution_clause": "§2.2 Privacy by Default",
                },
            )
        except Exception:
            pass  # audit must never cause the caller to silently proceed — we still raise above


def get_router(
    primary_name: str | None = None,
    cheap_name: str | None = None,
    local_name: str | None = "ollama",
) -> ModelRouter:
    """Build a ModelRouter from the global registry."""
    registry = get_registry()
    primary = registry.get_available(prefer=primary_name)
    try:
        cheap = registry.get_available(prefer=cheap_name)
    except Exception:
        cheap = primary

    local: ModelInterface | None = None
    if local_name:
        try:
            local = registry.get(local_name)
            if not local.is_available():
                local = None
        except Exception:
            local = None

    return ModelRouter(primary=primary, cheap=cheap, local=local)

