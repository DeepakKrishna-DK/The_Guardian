"""
Guardian Core Orchestrator
===========================
The central component of AI Guardian. Receives user input, manages
conversation context, calls the model, and returns a structured response.

Constitution reference:
  Section 7 — Standard Work Cycle
  Goal -> Understand -> Plan -> Select -> Execute -> Verify -> Report

Current implementation (Phase 3): simplest reliable version.
  - Single model backend (no multi-agent routing yet)
  - In-session working memory (no persistent memory yet)
  - No tools yet (Phase 7)
  - No skill routing yet (Phase 5)

Purpose:    Central processing loop for all Guardian interactions
Inputs:     str (user goal/message) + active Session
Outputs:    GuardianResponse
Deps:       guardian.model, guardian.core.session, guardian.core.response
Permissions: Level 0 for queries; Level 1/2 gates applied to future tool calls
Failure:    Returns GuardianResponse with error field; never raises to caller
"""

from __future__ import annotations

import time
from typing import Any

from guardian.core.response import GuardianResponse
from guardian.core.session import Session
from guardian.logging.logger import get_logger
from guardian.model.router import CallType
from guardian.model.interface import (
    ModelError,
    ModelInterface,
    ModelRequest,
)
from guardian.prompts import GUARDIAN_MASTER_SYSTEM_PROMPT_V1 as GUARDIAN_SYSTEM_PROMPT  # v1.0 default

log = get_logger(__name__)

# Soft limit on user input length (chars). Inputs beyond this are flagged.
MAX_INPUT_CHARS = 32_000


class InputError(ValueError):
    """Raised when user input fails validation."""


class GuardianCore:
    """
    Central orchestrator for AI Guardian.

    Usage:
        from guardian.model.registry import get_model
        from guardian.core.orchestrator import GuardianCore
        from guardian.core.session import Session

        core = GuardianCore(model=get_model())
        session = Session()
        response = core.process("What is the capital of France?", session)
        print(response.content)

    The caller is responsible for creating and maintaining the Session.
    This allows the same GuardianCore to serve multiple sessions concurrently.
    """

    def __init__(
        self,
        model = None,
        system_prompt: str = GUARDIAN_SYSTEM_PROMPT,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        enable_self_critique: bool = False,
        router = None,
    ) -> None:
        try:
            from guardian.security.gateway import SecurityGateway
            self._gateway = SecurityGateway()
        except Exception:
            print("WARNING: Failed to init SecurityGateway")
            self._gateway = None
        if router is None and model is not None:
            from guardian.model.router import ModelRouter
            router = ModelRouter(primary=model)
        elif router is None and model is None:
            raise ValueError("Must provide either model or router")
            
        self._router = router
        self._model = self._router.primary
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._enable_self_critique = enable_self_critique

        info = self._model.get_info()
        log.info(
            f"GuardianCore initialised: provider={info.provider} "
            f"model={info.model} available={info.available}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        user_input: str,
        session: Session,
        active_skill: str = "guardian",
        skill_prompt_addition: str = "",
        call_type: CallType = CallType.ROUTINE,
    ) -> GuardianResponse:
        """
        Process one user message and return a structured response.

        Steps:
          1. Validate input
          2. Build model request (with session history + optional skill prompt)
          3. Call model
          4. Record turn in session
          5. Return GuardianResponse

        Args:
            active_skill           Name of active skill (for logging/response)
            skill_prompt_addition  Additional prompt text from the active skill

        Never raises — errors are captured in GuardianResponse.error.
        """
        turn_number = session.next_turn_number
        log.info(f"Processing turn {turn_number} [{active_skill}]: {len(user_input)} chars")

        if hasattr(self, '_gateway') and self._gateway is not None:
            user_id = getattr(session, 'user_id', 'anonymous')
            gw_result = self._gateway.check_request(user_input=user_input, user_id=user_id, session_id="")
            if not gw_result.allowed:
                return self._error_response(gw_result.reason, turn_number)
            user_input = gw_result.sanitized_input

        # Step 1 — Validate
        try:
            self._validate_input(user_input)
        except InputError as exc:
            log.warning(f"Input validation failed: {exc}")
            return self._error_response(str(exc), turn_number)

        # Step 1b — Input guardrails (blocks prompt injection, etc.)
        try:
            from guardian.guardrails import get_guardrails_layer
            _gr = get_guardrails_layer()
            _gr_in = _gr.scan_input(user_input)
            if _gr_in.blocked:
                log.warning(f"Guardrails BLOCKED input on turn {turn_number}")
                try:
                    from guardian.audit import get_audit_log
                    get_audit_log().append(
                        "guardrail.input_blocked",
                        session_id=str(session.session_id) if hasattr(session, "session_id") else "",
                        payload={"turn": turn_number, "rule_count": len(_gr_in.violations)},
                    )
                except Exception:
                    pass
                return self._error_response(
                    _gr.block_message(_gr_in), turn_number
                )
        except Exception as _gr_exc:
            log.debug(f"Guardrails input scan skipped: {_gr_exc}")

        # Steps 2 & 3 — Build request and call model
        t0 = time.monotonic()
        try:
            request = self._build_request(user_input, session, skill_prompt_addition)

            # Evaluate skill via PolicyEngine (as a pseudo-tool)
            from guardian.policy.engine import Effect, get_policy_engine
            from guardian.skills import get_skill_registry
            from guardian.audit import get_audit_log
            
            skill_obj = get_skill_registry().get_or_default(active_skill)
            
            # Audit request
            try:
                get_audit_log().append(
                    "skill.request",
                    session_id=str(session.session_id) if hasattr(session, "session_id") else "",
                    payload={"skill": skill_obj.name, "turn": turn_number},
                )
            except Exception:
                pass

            engine = get_policy_engine()
            skill_decision = engine.evaluate(
                tool_name=f"skill:{skill_obj.name}",
                tool_level=skill_obj.risk_tier,
                params={},
                registered_tools={f"skill:{skill_obj.name}"},
                target_arg=None, # Skills don't natively take dynamic target_arg in process() yet
                requires_scope=skill_obj.requires_scope,
            )

            # Audit result
            try:
                get_audit_log().append(
                    "skill.result",
                    session_id=str(session.session_id) if hasattr(session, "session_id") else "",
                    payload={"skill": skill_obj.name, "effect": skill_decision.effect.name, "reason": skill_decision.reason},
                )
            except Exception:
                pass

            if skill_decision.effect != Effect.ALLOW:
                return self._error_response(
                    f"Skill Blocked: {skill_decision.reason}", turn_number
                )

            # Get the appropriate model from the router, enforcing local_only constraint if needed
            try:
                target_model = self._router.route(call_type, require_local=skill_obj.local_only)
            except Exception as e:
                # If router fails to find a local model when required, fail closed
                return self._error_response(str(e), turn_number)

            # Enforce local-only routing through the authoritative policy engine
            policy_decision = engine.evaluate_model_call(
                active_skill=active_skill,
                backend_locality=getattr(target_model, "locality", "unknown")
            )

            if policy_decision.effect == Effect.DENY:
                return self._error_response(
                    f"Policy Deny: {policy_decision.reason}",
                    turn_number
                )

            # M3: Escalation / Collaboration Check
            # Use Planner to verify intent if it looks like an action rather than a simple chat
            if call_type == CallType.ROUTINE and ("scan" in user_input.lower() or "execute" in user_input.lower() or "*" in user_input):
                from guardian.core.planning import Planner
                from guardian.core.collab import Escalation, EscalationReason
                planner = Planner(self)
                plan = planner.create_plan(user_input, session)
                if plan and plan.steps:
                    warnings = planner.verify_plan(plan)
                    if warnings:
                        escalations = []
                        for w in warnings:
                            reason = EscalationReason.POLICY_APPROVAL_REQUIRED
                            if "scope" in w.lower() or "*" in user_input:
                                reason = EscalationReason.AMBIGUOUS_SCOPE
                            escalations.append(Escalation(reason=reason, message=w, pending_action="Provide clarification or approve"))
                        
                        return GuardianResponse(
                            content="Escalation required: I need clarification or approval before proceeding with this action.",
                            model_provider="guardian",
                            model_name="orchestrator",
                            session_turn=turn_number,
                            duration_ms=(time.monotonic() - t0) * 1000,
                            escalations=escalations
                        )

            model_response = target_model.complete(request)
            
            # M4: Token cost tracking (audit only)
            try:
                from guardian.audit import get_audit_log
                u = model_response.usage
                
                # Small updatable pricing table (cost per 1M tokens)
                PRICING = {
                    "gemini-2.5-flash": {"prompt": 0.075, "completion": 0.30},
                    "llama3-8b-8192": {"prompt": 0.05, "completion": 0.08},
                }
                
                cost = 0.0
                model_name = getattr(self._model, "name", "unknown")
                if u and model_name in PRICING:
                    rates = PRICING[model_name]
                    cost = (u.prompt_tokens / 1_000_000 * rates["prompt"]) + (u.completion_tokens / 1_000_000 * rates["completion"])
                    
                if u:
                    get_audit_log().append(
                        "model.usage",
                        session_id=str(session.session_id) if hasattr(session, "session_id") else "",
                        payload={
                            "model": model_name,
                            "prompt_tokens": u.prompt_tokens,
                            "completion_tokens": u.completion_tokens,
                            "total_tokens": u.total_tokens,
                            "estimated_cost_usd": round(cost, 6)
                        }
                    )
            except Exception as e:
                log.warning(f"Failed to audit model usage: {e}")
                
        except ModelError as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            log.error(f"Model error on turn {turn_number}: {exc}")
            return self._error_response(
                str(exc), turn_number, duration_ms=duration_ms
            )
        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            log.error(f"Unexpected error on turn {turn_number}: {type(exc).__name__}: {exc}")
            return self._error_response(
                f"Unexpected error: {type(exc).__name__}: {exc}",
                turn_number,
                duration_ms=duration_ms,
            )

        duration_ms = (time.monotonic() - t0) * 1000
        content = model_response.content
        
        # M6: Advisory self-critique pass (if enabled)
        if self._enable_self_critique and content and len(content) > 10:
            try:
                critique_prompt = f"Critique this response for safety and accuracy. Output 'SAFE' or 'UNSAFE: <reason>'.\n\nResponse:\n{content}"
                critique_req = ModelRequest(messages=[{"role": "user", "content": critique_prompt}])
                critique_res = self._router.route(call_type).complete(critique_req)
                is_unsafe = "UNSAFE" in (critique_res.content or "").upper()
                
                try:
                    from guardian.audit import get_audit_log
                    get_audit_log().append(
                        "model.self_critique",
                        session_id=str(session.session_id) if hasattr(session, "session_id") else "",
                        payload={
                            "unsafe": is_unsafe,
                            "critique_length": len(critique_res.content or "")
                        }
                    )
                except Exception:
                    pass
            except Exception as e:
                log.warning(f"Self-critique failed: {e}")

        # Audit: model.call — metadata only, NO prompt or response text
        try:
            from guardian.audit import get_audit_log
            get_audit_log().append(
                "model.call",
                session_id=str(session.session_id) if hasattr(session, "session_id") else "",
                payload={
                    "provider": model_response.provider,
                    "model": model_response.model,
                    "locality": getattr(self._model, "locality", "unknown"),
                    "duration_ms": round(duration_ms, 1),
                    "tokens": model_response.usage.total_tokens,
                    "turn": turn_number,
                },
            )
        except Exception:
            pass

        # Step 3b — Output guardrails (redact secrets/PII from model output)
        try:
            from guardian.guardrails import get_guardrails_layer
            _gr_out = get_guardrails_layer().scan_output(content)
            if _gr_out.violations:
                content = _gr_out.sanitised_text
                log.warning(f"Guardrails sanitised output on turn {turn_number}")
                try:
                    from guardian.audit import get_audit_log
                    get_audit_log().append(
                        "guardrail.output_redacted",
                        session_id=str(session.session_id) if hasattr(session, "session_id") else "",
                        payload={"turn": turn_number, "violation_count": len(_gr_out.violations)},
                    )
                except Exception:
                    pass
        except Exception as _gr_exc:
            log.debug(f"Guardrails output scan skipped: {_gr_exc}")

        # Step 4 — Record in session
        session.add_turn(
            user_message=user_input,
            assistant_reply=content,
            model_provider=model_response.provider,
            model_name=model_response.model,
            duration_ms=duration_ms,
            tokens_used=model_response.usage.total_tokens,
        )

        # Step 5 — Return
        response = GuardianResponse(
            content=content,
            model_provider=model_response.provider,
            model_name=model_response.model,
            session_turn=turn_number,
            duration_ms=duration_ms,
            tokens_used=model_response.usage.total_tokens,
            active_skill=active_skill,
        )

        log.info(f"Turn {turn_number} complete: {response.summary()}")
        return response

    def get_model_info(self) -> dict[str, Any]:
        """Return metadata about the current model backend."""
        info = self._model.get_info()
        return {
            "provider": info.provider,
            "model": info.model,
            "available": info.available,
            "is_local": info.is_local,
            "requires_key": info.requires_key,
        }

    def swap_model(self, new_model: ModelInterface) -> None:
        """
        Replace the model backend at runtime.
        Constitution section 10: model must be replaceable without
        redesigning the rest of the system.
        """
        old_info = self._model.get_info()
        new_info = new_model.get_info()
        log.info(
            f"Model swap: {old_info.provider}/{old_info.model} "
            f"-> {new_info.provider}/{new_info.model}"
        )
        self._model = new_model
        if hasattr(self, '_router'):
            from guardian.model.router import ModelRouter
            self._router = ModelRouter(primary=new_model)



    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_input(self, user_input: str) -> None:
        """Validate user input before sending to the model."""
        if not user_input or not user_input.strip():
            raise InputError("Input must not be empty.")
        if len(user_input) > MAX_INPUT_CHARS:
            raise InputError(
                f"Input too long: {len(user_input)} chars "
                f"(limit: {MAX_INPUT_CHARS})"
            )

    def _build_request(
        self, user_input: str, session: Session, skill_addition: str = ""
    ) -> ModelRequest:
        """Build the ModelRequest including conversation history and skill prompt."""
        messages = session.to_messages_with_next(user_input)
        system_prompt = self._system_prompt
        if skill_addition:
            system_prompt = f"{system_prompt}\n\n{skill_addition}"
        return ModelRequest(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )

    def _error_response(
        self,
        error_msg: str,
        turn_number: int,
        duration_ms: float = 0.0,
    ) -> GuardianResponse:
        info = self._model.get_info()
        return GuardianResponse(
            content="",
            model_provider=info.provider,
            model_name=info.model,
            session_turn=turn_number,
            duration_ms=duration_ms,
            error=error_msg,
        )
