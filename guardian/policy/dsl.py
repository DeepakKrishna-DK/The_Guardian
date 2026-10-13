from dataclasses import dataclass, field
from typing import Any
import yaml
from pathlib import Path
import re
from datetime import datetime, timezone
from guardian.policy.engine import PolicyDecision, Effect, _check_scope, _load_scope

@dataclass
class DSLRule:
    id: str
    description: str
    condition: dict[str, Any]
    effect: str
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> list["DSLRule"]:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        rules = []
        for r in data.get("rules", []):
            rules.append(cls(
                id=r.get("id", ""),
                description=r.get("description", ""),
                condition=r.get("condition", {}),
                effect=r.get("effect", "deny"),
                risk_flags=r.get("risk_flags", [])
            ))
        return rules

class DSLEngine:
    def __init__(self, rules: list[DSLRule]):
        self.rules = rules
        
    def evaluate(self, 
                 tool_name: str, 
                 tool_level: int, 
                 params: dict[str, Any], 
                 registered_tools: set[str], 
                 requires_scope: bool,
                 cfg: Any,
                 target_arg: str | None = None) -> PolicyDecision:
        
        flags = []
        
        for rule in self.rules:
            matched, scope_reason, auth_basis = self._evaluate_condition(rule.condition, tool_name, tool_level, params, registered_tools, requires_scope, cfg, target_arg)
            if matched:
                flags.extend(rule.risk_flags)
                if rule.effect == "deny":
                    reason = f"matched {rule.id}: {rule.description}"
                    if scope_reason:
                        reason += f" ({scope_reason})"
                    return PolicyDecision(Effect.DENY, rule.id, reason, risk_flags=flags, auth_basis=auth_basis)
                elif rule.effect == "require_approval":
                    return PolicyDecision(Effect.REQUIRE_APPROVAL, rule.id, f"tool level {tool_level}: requires approval", risk_flags=flags, auth_basis=auth_basis)
                elif rule.effect == "allow":
                    # M3 says identical behaviour. We can return allow if it's risk tier 0. 
                    # Wait, if rule 4 evaluates to allow, we can return it.
                    return PolicyDecision(Effect.ALLOW, rule.id, f"tool level {tool_level}: auto-allow", risk_flags=flags, auth_basis=auth_basis)
                elif rule.effect == "flag_only":
                    # just collect flags and continue
                    continue
                    
        # Default allow if no deny (but wait, M3 says re-express ALL 5 rules)
        # We should just return whatever the last rule produced if it reached here, but in my DSL, the first deny/allow returns.
        return PolicyDecision(Effect.ALLOW, "default.allow", "no rule matched", risk_flags=flags)

    def _evaluate_condition(self, cond: dict, tool_name: str, tool_level: int, params: dict, registered_tools: set[str], requires_scope: bool, cfg: Any, target_arg: str | None) -> tuple[bool, str, dict|None]:
        if "not_registered" in cond:
            return tool_name not in registered_tools, "", None
            
        if "blocklist_allowlist" in cond:
            if tool_name in cfg.blocked_tools:
                return True, "tool is blocked by policy", None
            if cfg.allowlist and tool_name not in cfg.allowlist:
                return True, "tool not in allowlist", None
            return False, "", None
            
        if "requires_scope" in cond:
            if requires_scope:
                target = str(params.get(target_arg or "target", "")) if target_arg else ""
                scope_ok, scope_reason, auth = _check_scope(target, cfg.scope_file, cfg.scope_hmac_key, cfg.require_signature)
                if not scope_ok:
                    return True, scope_reason, None
                return False, "", auth
            return False, "", None
            
        if "risk_tier" in cond:
            tier_cond = cond["risk_tier"]
            if tier_cond == ">0" and tool_level > 0:
                return True, "", None
            if tier_cond == "==0" and tool_level == 0:
                return True, "", None
            return False, "", None
            
        if "shell_meta" in cond:
            command = params.get("command", "")
            if isinstance(command, str) and re.search(r'[|&;<>$`\\]', command):
                return True, "", None
            return False, "", None
            
        return False, "", None
