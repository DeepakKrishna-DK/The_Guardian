"""
Guardian Gateway Choke Point
============================
Enforces identical security pipeline for all inbound remote requests:
  Inbound:
    Input Guardrails (Prompt injection, secret leaks, toxicity)
    -> SecurityGateway (Auth, rate limit, input firewall, risk engine, canary probe)
    -> GuardianCore (Session, Model, PolicyEngine DSL rules, ToolExecutor permission tiers)
  Outbound:
    SecurityGateway (Output firewall, canary exfiltration check)
    -> Output Guardrails (PII redaction)

Remote access is purely a transport; it NEVER bypasses authorization or safety gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from guardian.core.orchestrator import GuardianCore
from guardian.core.session import Session
from guardian.core.response import GuardianResponse
from guardian.logging.logger import get_logger
from guardian.model.registry import get_model
from guardian.security.gateway import SecurityGateway, GatewayResult

log = get_logger(__name__)


@dataclass
class GatewayProcessingResult:
    success: bool
    content: str
    session_id: str
    error: Optional[str] = None
    blocked_by: Optional[str] = None
    tools_called: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class GatewayChokePoint:
    """
    Central choke point executing the unified security and orchestration loop.
    """

    def __init__(self, core: Optional[GuardianCore] = None, gateway: Optional[SecurityGateway] = None):
        self.gateway = gateway or SecurityGateway()
        if core is None:
            try:
                model = get_model()
                self.core = GuardianCore(model=model)
            except Exception as e:
                log.warning(f"Using default fallback model for GatewayChokePoint: {e}")
                from guardian.model.backends.mock import MockBackend
                self.core = GuardianCore(model=MockBackend(response_prefix="[MOCK]"))
        else:
            self.core = core

    def process_remote_request(
        self,
        user_input: str,
        device_id: str,
        device_name: str,
        session_id: Optional[str] = None,
        token: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> GatewayProcessingResult:
        """
        Processes a remote request through the complete multi-tier safety pipeline.
        """
        # 1. Input Guardrails & Security Gateway screening
        gw_res: GatewayResult = self.gateway.check_request(
            user_input=user_input,
            user_id=f"device:{device_id}",
            session_id=session_id or "",
            token=token,
        )

        if not gw_res.allowed:
            log.warning(f"Remote request blocked at SecurityGateway: {gw_res.reason} (Device: {device_id})")
            return GatewayProcessingResult(
                success=False,
                content="",
                session_id=session_id or "",
                error=gw_res.reason,
                blocked_by="security_gateway",
            )

        sanitized_input = gw_res.sanitized_input or user_input

        # 2. Session initialization
        if session is None:
            session = Session()

        effective_session_id = session_id or getattr(session, "session_id", "default_session")

        # 3. Core Orchestration (Model + PolicyEngine + ToolExecutor)
        try:
            resp: GuardianResponse = self.core.process(
                user_input=sanitized_input,
                session=session,
            )
        except Exception as e:
            log.exception(f"Unexpected error in GuardianCore during remote processing: {e}")
            return GatewayProcessingResult(
                success=False,
                content="",
                session_id=effective_session_id,
                error=f"Processing error: {str(e)}",
                blocked_by="orchestrator",
            )

        raw_output = resp.content or ""

        # 4. Outbound Security Gateway inspection (Canary exfiltration, secrets)
        if gw_res.context:
            out_res: GatewayResult = self.gateway.check_output(raw_output, gw_res.context)
            if not out_res.allowed:
                log.warning(f"Remote output blocked at SecurityGateway: {out_res.reason}")
                return GatewayProcessingResult(
                    success=False,
                    content="",
                    session_id=effective_session_id,
                    error=out_res.reason,
                    blocked_by="output_firewall",
                )
            final_output = out_res.sanitized_output or raw_output
        else:
            final_output = raw_output

        is_success = resp.is_success if hasattr(resp, "is_success") else (not bool(resp.error))
        blocked_by = "guardrails" if resp.error and any(k in resp.error.lower() for k in ("block", "override", "guidelines", "guardrail", "policy")) else ("orchestrator" if resp.error else None)

        return GatewayProcessingResult(
            success=is_success,
            content=final_output,
            session_id=effective_session_id,
            error=resp.error,
            blocked_by=blocked_by,
            tools_called=[],
            metadata={
                "device_id": device_id,
                "device_name": device_name,
                "latency_ms": getattr(resp, "latency_ms", 0.0),
            },
        )
