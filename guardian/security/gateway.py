import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from .auth import get_auth_layer
from .rate_limiter import get_rate_limiter
from .firewall import get_firewall
from .pii_detector import get_pii_detector
from .risk_engine import get_risk_engine
from .output_firewall import get_output_firewall
from .kill_switch import get_kill_switch, KillSwitchTriggeredError
from .circuit_breaker import get_circuit_breaker

try:
    from .canary import get_canary_manager
except ImportError:
    get_canary_manager = None

try:
    from guardian.audit.log import AuditLog
except ImportError:
    AuditLog = None

@dataclass
class SecurityContext:
    request_id: str
    user_id: str
    tenant_id: str
    authentication_status: bool
    risk_level: str
    data_classification: str
    security_flags: List[str]
    allowed_tools: Set[str]
    rate_limit_status: str
    policy_decision: str
    audit_context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GatewayResult:
    allowed: bool
    context: Optional[SecurityContext]
    reason: str
    sanitized_output: Optional[str]
    sanitized_input: str

class SecurityGateway:
    def __init__(self):
        self.auth = get_auth_layer()
        self.rate_limiter = get_rate_limiter()
        self.firewall = get_firewall()
        self.pii = get_pii_detector()
        self.risk = get_risk_engine()
        self.output_fw = get_output_firewall()
        self.kill_switch = get_kill_switch()
        self.circuit_breaker = get_circuit_breaker()
        self.audit = AuditLog() if AuditLog else None
        try:
            self.canary = get_canary_manager() if get_canary_manager else None
        except Exception:
            self.canary = None

    def audit_event(self, ctx: SecurityContext, event_type: str, payload: dict):
        if self.audit:
            try:
                self.audit.log(event_type=event_type, user_id=ctx.user_id, **payload)
            except Exception:
                pass
                
    def check_request(self, user_input: str, user_id: str, session_id: str = "", token: str = None) -> GatewayResult:
        try:
            if self.kill_switch.is_active():
                raise KillSwitchTriggeredError("Kill switch is active")
                
            if self.circuit_breaker.is_open("gateway"):
                return GatewayResult(allowed=False, context=None, reason="Circuit breaker open", sanitized_output=None, sanitized_input=user_input)

            # Canary probe check
            if self.canary:
                leaked_canaries = self.canary.inspect_text_leak(user_input)
                if leaked_canaries:
                    return GatewayResult(
                        allowed=False,
                        context=None,
                        reason="Intrusion alert: Canary token probed in input",
                        sanitized_output=None,
                        sanitized_input=user_input,
                    )
                
            req_id = str(uuid.uuid4())
            ctx = SecurityContext(
                request_id=req_id,
                user_id=user_id,
                tenant_id="",
                authentication_status=False,
                risk_level="low",
                data_classification="public",
                security_flags=[],
                allowed_tools=set(),
                rate_limit_status="ok",
                policy_decision="allow"
            )
            
            # Auth
            uctx = self.auth.get_user_context(user_id, token)
            ctx.user_id = uctx.user_id
            ctx.tenant_id = uctx.tenant_id
            ctx.authentication_status = uctx.is_authenticated
            
            # Rate limit
            rl = self.rate_limiter.check(ctx.user_id)
            if not rl.allowed:
                ctx.rate_limit_status = "limited"
                self.audit_event(ctx, "RATE_LIMIT", {"reason": rl.limit_type})
                return GatewayResult(allowed=False, context=ctx, reason="Rate limit exceeded", sanitized_output=None, sanitized_input=user_input)
                
            # Input firewall
            fw_res = self.firewall.inspect(user_input)
            if fw_res.blocked:
                self.audit_event(ctx, "FIREWALL_BLOCK", {"threats": fw_res.threats})
                return GatewayResult(allowed=False, context=ctx, reason="Input blocked by firewall", sanitized_output=None, sanitized_input=user_input)
                
            # PII
            pii_res = self.pii.detect(fw_res.redacted_text)
            
            # Risk
            risk_res = self.risk.evaluate(user_input, {"is_authenticated": ctx.authentication_status}, firewall_result=fw_res, pii_result=pii_res)
            ctx.risk_level = risk_res.risk_level
            ctx.policy_decision = risk_res.decision
            
            if risk_res.decision == "deny":
                self.audit_event(ctx, "POLICY_DENY", {"reasons": risk_res.reasons})
                return GatewayResult(allowed=False, context=ctx, reason="Request denied by risk engine", sanitized_output=None, sanitized_input=user_input)
                
            self.circuit_breaker.record_success("gateway")
            return GatewayResult(allowed=True, context=ctx, reason="", sanitized_output=None, sanitized_input=pii_res.redacted_text)
            
        except KillSwitchTriggeredError as e:
            return GatewayResult(allowed=False, context=None, reason=str(e), sanitized_output=None, sanitized_input=user_input)
        except Exception as e:
            self.circuit_breaker.record_failure("gateway", str(e))
            return GatewayResult(allowed=False, context=None, reason="Internal error - failed closed", sanitized_output=None, sanitized_input=user_input)
            
    def check_output(self, output: str, ctx: SecurityContext) -> GatewayResult:
        try:
            # Canary exfiltration interception
            if self.canary:
                leaked_canaries = self.canary.inspect_text_leak(output)
                if leaked_canaries:
                    self.audit_event(ctx, "CANARY_EXFILTRATION_BLOCKED", {"tokens": [t.name for t in leaked_canaries]})
                    return GatewayResult(allowed=False, context=ctx, reason="Intrusion alert: Canary secret exfiltration intercepted", sanitized_output=None, sanitized_input="")

            out_res = self.output_fw.inspect(output, {"risk_level": ctx.risk_level})
            if not out_res.allowed:
                self.audit_event(ctx, "OUTPUT_BLOCK", {"reasons": out_res.reasons})
                return GatewayResult(allowed=False, context=ctx, reason="Output blocked", sanitized_output=None, sanitized_input="")
            return GatewayResult(allowed=True, context=ctx, reason="", sanitized_output=out_res.sanitized_output, sanitized_input="")
        except Exception:
            return GatewayResult(allowed=False, context=ctx, reason="Output error - failed closed", sanitized_output=None, sanitized_input="")
