"""
Guardian Policy Engine — guardian/policy/engine.py
====================================================
Single choke-point for all tool call authorization.

Rules (evaluated in order):
  1. Unknown/unregistered tool → DENY
  2. Tool in blocked_tools list, or not in allowlist (when set) → DENY
  3. Scope: tools declaring requires_scope + target_arg need a valid
     signed scope file; target must be in-scope and within time window → DENY
  4. Risk tier: Level 0 → ALLOW; Level >= 1 → REQUIRE_APPROVAL
  5. risk_flags: shell metacharacters flagged (annotated, not blocked)

Fail-closed: any unhandled exception → DENY + audit event policy.error

Limitation (v1): no DNS resolution in scope checks. Targets must be
exact IPs, CIDRs, or *.domain wildcard patterns. Document this.

Apache-2.0.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# Shell metacharacters that warrant flagging (not blocking)
_SHELL_META_PATTERN = re.compile(r"[&|^%><;`$(\n]")


class Effect(Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True)
class PolicyDecision:
    effect: Effect
    rule_id: str
    reason: str
    risk_flags: list[str] = field(default_factory=list)
    auth_basis: dict | None = None

    @property
    def is_allowed(self) -> bool:
        return self.effect != Effect.DENY

    @property
    def requires_approval(self) -> bool:
        return self.effect == Effect.REQUIRE_APPROVAL


@dataclass
class PolicyConfig:
    """
    Runtime policy configuration.

    blocked_tools: tool names that are always denied
    allowlist: if non-empty, only these tool names are permitted
    scope_file: path to JSON scope file (GUARDIAN_SCOPE_FILE env overrides)
    scope_hmac_key: HMAC-SHA256 key for scope signature verification
    require_signature: if True, scope file must have valid HMAC signature
    """
    blocked_tools: list[str] = field(default_factory=list)
    allowlist: list[str] = field(default_factory=list)
    scope_file: str | None = None
    scope_hmac_key: str | None = None
    require_signature: bool = False

    @classmethod
    def from_env(cls) -> "PolicyConfig":
        return cls(
            scope_file=os.environ.get("GUARDIAN_SCOPE_FILE"),
            scope_hmac_key=os.environ.get("GUARDIAN_SCOPE_HMAC_KEY"),
        )


def _load_scope(scope_file: str | None, hmac_key: str | None, require_sig: bool) -> dict[str, Any] | None:
    """Load and optionally verify a scope JSON file. Returns None on any failure."""
    if not scope_file:
        return None
    try:
        data = json.loads(Path(scope_file).read_text(encoding="utf-8"))
    except Exception:
        return None

    # HMAC signature verification
    if require_sig or hmac_key:
        sig = data.get("signature", "")
        if not sig:
            if require_sig:
                return None
        else:
            if not hmac_key:
                return None
            # Canonical form: everything except "signature"
            canon = {k: v for k, v in data.items() if k != "signature"}
            canon_bytes = json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
            expected = hmac.new(hmac_key.encode(), canon_bytes, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, sig):
                return None

    return data  # type: ignore[no-any-return]


def _target_in_scope(target: str, scope_targets: list[str]) -> bool:
    """
    Return True if target matches any entry in scope_targets.

    Entries can be:
      - Exact IP or hostname: "10.0.0.1", "example.com"
      - CIDR: "192.168.1.0/24"
      - Wildcard subdomain: "*.example.com" matches "sub.example.com" but NOT "example.com"

    v1 limitation: no DNS resolution. Targets are matched as strings/CIDRs only.
    """
    for entry in scope_targets:
        if entry.startswith("*."):
            # Wildcard: matches *.domain → sub.domain only, NOT domain itself
            apex = entry[2:]  # "example.com"
            if target != apex and target.endswith("." + apex):
                return True
        elif "/" in entry:
            # CIDR range
            try:
                if ipaddress.ip_address(target) in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                pass  # target is not an IP
        else:
            # Exact match
            if target == entry:
                return True
    return False


def _check_scope(
    target: str,
    scope_file: str | None,
    hmac_key: str | None,
    require_sig: bool,
) -> tuple[bool, str, dict | None]:
    """
    Returns (allowed: bool, reason: str).
    Fail closed: no scope loaded -> deny.
    """
    scope = _load_scope(scope_file, hmac_key, require_sig)
    if scope is None:
        return False, "no valid scope file loaded", None

    # M1: Compliance Attestation Layer - Check authorization_basis
    auth_basis = scope.get("authorization_basis")
    if not auth_basis:
        return False, "scope missing required authorization_basis", None
    
    date_str = auth_basis.get("date")
    if not date_str:
        return False, "authorization_basis missing date", None
        
    try:
        auth_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if (now - auth_date).days > 90:
            return False, "authorization_basis expired (> 90 days)", None
    except ValueError:
        return False, "authorization_basis has invalid date format", None

    # Time window check
    now = datetime.now(timezone.utc)
    not_before = scope.get("not_before")
    not_after = scope.get("not_after")
    if not_before:
        try:
            nb = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
            if now < nb:
                return False, f"scope window not yet open (not_before={not_before})", None
        except ValueError:
            return False, "invalid not_before format in scope", None
    if not_after:
        try:
            na = datetime.fromisoformat(not_after.replace("Z", "+00:00"))
            if now > na:
                return False, f"scope window expired (not_after={not_after})", None
        except ValueError:
            return False, "invalid not_after format in scope", None

    targets = scope.get("targets", [])
    if not _target_in_scope(target, targets):
        return False, f"target {target!r} not in scope", None

    return True, "", auth_basis


class PolicyEngine:
    """
    Evaluates tool calls against the configured policy.

    Usage:
        engine = PolicyEngine(config=PolicyConfig())
        decision = engine.evaluate(
            tool_name="shell",
            tool_level=2,
            params={"command": "ls"},
            registered_tools={"shell", "file_read"},
        )
    """

    def __init__(self, config: PolicyConfig | None = None) -> None:
        self._config = config or PolicyConfig.from_env()

    def evaluate(
        self,
        tool_name: str,
        tool_level: int,
        params: dict[str, Any],
        registered_tools: set[str],
        target_arg: str | None = None,
        requires_scope: bool = False,
    ) -> PolicyDecision:
        """
        Evaluate a tool call. Fail closed: any exception → DENY.

        Args:
            tool_name: name of the tool being called
            tool_level: ToolLevel integer (0=READ, 1=WRITE, 2=DANGEROUS)
            params: tool parameters dict
            registered_tools: set of currently registered tool names
            target_arg: name of the param holding the network target (for scope check)
            requires_scope: whether this tool requires a valid scope file
        """
        try:
            return self._evaluate(tool_name, tool_level, params, registered_tools, target_arg, requires_scope)
        except Exception as exc:
            return PolicyDecision(
                effect=Effect.DENY,
                rule_id="policy.error",
                reason=f"policy evaluation error: {exc}",
                risk_flags=["policy.error"],
            )

    def _evaluate(
        self,
        tool_name: str,
        tool_level: int,
        params: dict[str, Any],
        registered_tools: set[str],
        target_arg: str | None,
        requires_scope: bool,
    ) -> PolicyDecision:
        cfg = self._config
        
        # Load DSL rules
        from guardian.policy.dsl import DSLEngine, DSLRule
        
        # In a real scenario, this would load from a yaml file. We'll define them here to guarantee identical behavior.
        default_rules = [
            DSLRule("rule.1.unknown_tool", f"tool {tool_name!r} is not registered", {"not_registered": True}, "deny"),
            DSLRule("rule.2.blocklist", "blocklist/allowlist", {"blocklist_allowlist": True}, "deny"),
            DSLRule("rule.3.scope", "scope check failed", {"requires_scope": True}, "deny"),
            DSLRule("rule.5.risk_flags", "shell metacharacters", {"shell_meta": True}, "flag_only", ["shell.metacharacters"]),
            DSLRule("rule.4.risk_tier_high", "tool level > 0", {"risk_tier": ">0"}, "require_approval"),
            DSLRule("rule.4.risk_tier_low", "tool level == 0", {"risk_tier": "==0"}, "allow"),
        ]
        
        dsl_engine = DSLEngine(default_rules)
        return dsl_engine.evaluate(tool_name, tool_level, params, registered_tools, requires_scope, cfg, target_arg)

    def evaluate_model_call(self, active_skill: str, backend_locality: str) -> PolicyDecision:
        """
        Evaluate if a model call is allowed based on the active skill and backend locality.
        Enforces the "Security data stays local" constraint for any skill marked local_only.
        """
        from guardian.skills import get_skill_registry
        
        # Find the active skill to see if it requires local execution
        skill_obj = get_skill_registry().get(active_skill)
        requires_local = skill_obj.local_only if skill_obj else False

        if requires_local and backend_locality != "local":
            return PolicyDecision(
                effect=Effect.DENY,
                rule_id="model.locality",
                reason=f"Skill '{active_skill}' requires a local model, but backend locality is '{backend_locality}'.",
                risk_flags=["cloud.leak_risk"]
            )

        return PolicyDecision(
            effect=Effect.ALLOW,
            rule_id="model.locality",
            reason="Model locality complies with skill sensitivity."
        )


# ── Singleton ─────────────────────────────────────────────────────────────────

_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    """Return the process-wide PolicyEngine singleton."""
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine


def reset_policy_engine(config: PolicyConfig | None = None) -> None:
    """Reset/reconfigure singleton (for tests)."""
    global _engine
    _engine = PolicyEngine(config) if config is not None else None

