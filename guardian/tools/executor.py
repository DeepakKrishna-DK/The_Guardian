"""
Guardian Tool Executor
=======================
Runs tools safely: validates requests, enforces authority levels,
checks sandbox boundaries, logs every invocation.

Constitution reference: Section 3 (Authority Model), Section 12 (Tools),
Section 11 (Transparency), Section 13 (Failure Policy)

Sandbox:
  All file-system paths are resolved relative to the workspace root.
  A path that resolves outside the workspace raises SandboxViolation.
  The sandbox root defaults to the Guardian project root.

Authority enforcement:
  Level 0 tools run immediately.
  Level 1 tools require ToolRequest.approved = True.
  Level 2 tools require ToolRequest.approved = True AND must be
  confirmed by the CLI layer before the request is even created.

Every invocation (success or failure) is logged at INFO level.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from guardian.logging.logger import get_logger
from guardian.tools.base import (
    SandboxViolation,
    Tool,
    ToolLevel,
    ToolRequest,
    ToolResult,
)

log = get_logger(__name__)

# Default sandbox root: Guardian project directory
_DEFAULT_SANDBOX = Path(__file__).resolve().parent.parent.parent


def _resolve_and_check(
    raw_path: str | Path, sandbox: Path
) -> Path:
    """
    Resolve a path and verify it is inside the sandbox.
    Raises SandboxViolation if the path escapes.
    """
    try:
        resolved = (sandbox / raw_path).resolve()
    except Exception as exc:
        raise SandboxViolation(f"Cannot resolve path {raw_path!r}: {exc}") from exc

    try:
        resolved.relative_to(sandbox.resolve())
    except ValueError:
        raise SandboxViolation(
            f"Path {raw_path!r} resolves to {resolved} "
            f"which is outside the sandbox {sandbox}"
        )
    return resolved


from collections import defaultdict, OrderedDict
import threading
import json
import hashlib

class TTLCache:
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        
    def get(self, key: str, ttl: float) -> ToolResult | None:
        with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.monotonic() - timestamp <= ttl:
                    self.cache.move_to_end(key)
                    return value
                else:
                    del self.cache[key]
            return None
            
    def put(self, key: str, value: ToolResult):
        with self.lock:
            self.cache[key] = (value, time.monotonic())
            self.cache.move_to_end(key)
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

_TOOL_CACHE = TTLCache(capacity=500)

def _get_cache_key(tool_name: str, params: dict) -> str:
    # Serialize params deterministically
    normalized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(f"{tool_name}:{normalized}".encode()).hexdigest()


class TokenBucket:
    def __init__(self, capacity: int = 10, fill_rate: float = 0.5):
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = float(capacity)
        self.last_fill = time.monotonic()
        
    def consume(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        self.tokens = min(float(self.capacity), self.tokens + (now - self.last_fill) * self.fill_rate)
        self.last_fill = now
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

class ToolExecutor:
    """
    Runs registered tools with authority checking and sandbox enforcement.

    Usage:
        executor = ToolExecutor(sandbox_root=project_root)
        executor.register(FileReadTool())
        result = executor.run(ToolRequest(name="file_read", params={"path": "README.md"}))
    """

    def __init__(self, sandbox_root: Path | None = None) -> None:
        self._sandbox = (sandbox_root or _DEFAULT_SANDBOX).resolve()
        self._tools: dict[str, Tool] = {}
        # M4: Rate limiter per (tool, session)
        self._rate_limiters: dict[tuple[str, str], TokenBucket] = defaultdict(lambda: TokenBucket(10, 0.5))
        self._rl_lock = threading.Lock()
        log.debug(f"ToolExecutor sandbox: {self._sandbox}")

    def register(self, tool: Tool) -> None:
        """Register a tool. Overwrites any existing tool with the same name."""
        self._tools[tool.name] = tool
        log.debug(f"Tool registered: {tool.name} (level={tool.level.name})")

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def run(self, request: ToolRequest) -> ToolResult:
        """
        Execute a tool request.

        Checks (in order):
          0. PolicyEngine.evaluate() — single authorization choke-point
          1. Tool is registered
          2. Authority level — Level 1+ require approved=True
          3. Tool executes within sandbox
          4. Result is logged
          Audit events: tool.request → policy.decision → (approval.requested
          → approval.granted|denied) → tool.result
        """
        # Audit: tool.request
        try:
            from guardian.audit import get_audit_log
            _audit = get_audit_log()
            
            # Context might be a string or a dict depending on who instantiated it
            actor = "guardian"
            if isinstance(request.context, dict):
                actor = request.context.get("actor", "guardian")

            _audit.append(
                "tool.request",
                actor=actor,
                payload={"tool": request.name, "context": request.context},
            )
        except Exception:
            _audit = None  # type: ignore[assignment]

        # M4: Rate limiter
        session_id = request.session_id or "default"
        with self._rl_lock:
            bucket = self._rate_limiters[(request.name, session_id)]
            if not bucket.consume():
                err = f"Rate limit exceeded for tool {request.name!r}."
                log.warning(err)
                if _audit is not None:
                    _audit.append("rate_limit.denied", payload={"tool": request.name, "session_id": session_id})
                return ToolResult(success=False, output="", error=err, tool_name=request.name)

        tool = self._tools.get(request.name)
        if tool is None:
            err = f"Unknown tool: {request.name!r}. Registered: {list(self._tools)}"
            log.error(err)
            return ToolResult(success=False, output="", error=err, tool_name=request.name)

        # Policy engine — single choke-point
        try:
            from guardian.policy import get_policy_engine
            _engine = get_policy_engine()
            registered = set(self._tools.keys())
            requires_scope = getattr(tool, "requires_scope", False)
            target_arg = getattr(tool, "target_arg", None)
            decision = _engine.evaluate(
                tool_name=request.name,
                tool_level=int(tool.level),
                params=request.params,
                registered_tools=registered,
                target_arg=target_arg,
                requires_scope=requires_scope,
            )
            # Audit: policy.decision
            if _audit is not None:
                payload = {
                    "tool": request.name,
                    "effect": decision.effect.value,
                    "rule_id": decision.rule_id,
                    "reason": decision.reason,
                    "risk_flags": decision.risk_flags,
                }
                if getattr(decision, "auth_basis", None):
                    payload["auth_basis"] = decision.auth_basis
                
                _audit.append(
                    "policy.decision",
                    payload=payload,
                )
            if decision.effect.value == "deny":
                err = f"Policy DENY [{decision.rule_id}]: {decision.reason}"
                log.warning(err)
                return ToolResult(success=False, output="", error=err, tool_name=request.name)
        except Exception as _pe:
            log.error(f"PolicyEngine error (fail-closed): {_pe}")
            return ToolResult(success=False, output="", error=f"Policy error: {_pe}", tool_name=request.name)

        # Authority gate (Level 1+ require approved=True from caller)
        if tool.level >= ToolLevel.WRITE:
            if _audit is not None:
                _audit.append("approval.requested", payload={"tool": request.name})
            if not request.approved:
                err = (
                    f"Tool {request.name!r} requires approval "
                    f"(level={tool.level.name}). "
                    f"Set ToolRequest.approved=True after user confirmation."
                )
                log.warning(err)
                if _audit is not None:
                    _audit.append("approval.denied", payload={"tool": request.name})
                return ToolResult(success=False, output="", error=err, tool_name=request.name)
            if _audit is not None:
                _audit.append("approval.granted", payload={"tool": request.name})

        # Inject sandbox into params so tools can call _check_path
        enriched_params: dict[str, Any] = dict(request.params)
        enriched_params["_sandbox"] = self._sandbox
        enriched_params["_resolve"] = _resolve_and_check

        # M4: Cache check
        ttl = getattr(tool, "cache_ttl", 0)
        cache_key = ""
        if ttl > 0:
            cache_key = _get_cache_key(request.name, request.params)
            cached_result = _TOOL_CACHE.get(cache_key, ttl)
            if cached_result:
                log.info(f"Tool cache HIT: {request.name}")
                if _audit is not None:
                    _audit.append("tool.cache_hit", payload={"tool": request.name})
                return cached_result

        log.info(
            f"Tool execute: {request.name} "
            f"level={tool.level.name} "
            f"context={request.context!r}"
        )

        t0 = time.monotonic()
        try:
            result = tool._execute(enriched_params)
        except SandboxViolation as exc:
            ms = (time.monotonic() - t0) * 1000
            log.warning(f"Sandbox violation in {request.name}: {exc}")
            return ToolResult(
                success=False, output="", error=f"Sandbox violation: {exc}",
                tool_name=request.name, duration_ms=ms,
            )
        except Exception as exc:
            ms = (time.monotonic() - t0) * 1000
            log.error(f"Unexpected error in tool {request.name}: {type(exc).__name__}: {exc}")
            return ToolResult(
                success=False, output="",
                error=f"Unexpected error: {type(exc).__name__}: {exc}",
                tool_name=request.name, duration_ms=ms,
            )

        result.duration_ms = (time.monotonic() - t0) * 1000
        result.tool_name = request.name

        # M4: Cache save
        if ttl > 0 and result.success:
            _TOOL_CACHE.put(cache_key, result)

        # M6(a): Wrap tool output as UNTRUSTED and scan for injection
        if result.success and result.output:
            _UNTRUSTED_OPEN = "[UNTRUSTED TOOL OUTPUT]"
            _UNTRUSTED_CLOSE = "[/UNTRUSTED TOOL OUTPUT]"
            try:
                from guardian.guardrails import get_guardrails_layer
                _scan = get_guardrails_layer().scan_input(result.output)
                if _scan.blocked or _scan.violations:
                    # Flag but do NOT block — add visible warning marker
                    warning_marker = "[WARNING: potential injection detected in tool output]"
                    result.output = (
                        f"{_UNTRUSTED_OPEN}\n{result.output}\n{_UNTRUSTED_CLOSE}\n{warning_marker}"
                    )
                    if _audit is not None:
                        _audit.append(
                            "tool.output.injection_suspected",
                            payload={"tool": request.name, "violation_count": len(_scan.violations)},
                        )
                    log.warning(f"Potential injection in output of tool {request.name!r}")
                else:
                    result.output = f"{_UNTRUSTED_OPEN}\n{result.output}\n{_UNTRUSTED_CLOSE}"
            except Exception:
                # Guardrails unavailable — still wrap as untrusted
                result.output = f"{_UNTRUSTED_OPEN}\n{result.output}\n{_UNTRUSTED_CLOSE}"

        # Audit: tool.result
        if _audit is not None:
            actor = "guardian"
            if isinstance(request.context, dict):
                actor = request.context.get("actor", "guardian")
                
            _audit.append(
                "tool.result",
                actor=actor,
                payload={
                    "tool": request.name,
                    "success": result.success,
                    "duration_ms": round(result.duration_ms or 0, 1),
                },
            )

        log.info(f"Tool result: {result.summary()}")
        return result

    @property
    def sandbox(self) -> Path:
        return self._sandbox
