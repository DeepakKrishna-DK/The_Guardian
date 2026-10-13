# ADR-0002: Policy Engine as Single Authorization Choke-Point

| Field    | Value                          |
|----------|-------------------------------|
| Status   | ACCEPTED                       |
| Date     | 2026-09-22                     |
| Deciders | Project owner                  |

## Context

Guardian executes tools (file operations, shell commands, web search, MCP-
exposed tools) on behalf of an LLM. Without a centralized policy gate, tool
invocations are scattered across the codebase, making it easy for a future
change to accidentally bypass authorization checks.

## Decision

Every tool call must pass through **one** choke-point: `PolicyEngine.evaluate()`
invoked from `ToolExecutor.run()` before the existing authority gate.

### Rules (ordered)

| # | Rule | Effect |
|---|------|--------|
| 1 | Tool not in registered set | DENY |
| 2 | Tool in `blocked_tools`, or allowlist set and tool not in it | DENY |
| 3 | Tool declares `requires_scope` and target not in valid signed scope file | DENY |
| 4 | `ToolLevel.READ` (0) | ALLOW |
| 4 | `ToolLevel.WRITE` (1) or `DANGEROUS` (2) | REQUIRE_APPROVAL |
| 5 | Shell metacharacters detected | flag `risk_flags` (never block) |

### Fail-closed contract

Any unhandled exception inside `PolicyEngine._evaluate()` is caught by
`evaluate()` and returns `PolicyDecision(DENY, "policy.error", ...)`.
This means a broken policy configuration denies all tool calls rather than
allowing them.

### Scope file format

```json
{
  "targets": ["192.168.1.0/24", "*.example.com", "10.0.0.1"],
  "not_before": "2026-01-01T00:00:00Z",
  "not_after":  "2026-12-31T23:59:59Z",
  "require_signature": false,
  "signature": ""
}
```

HMAC-SHA256 over `canonical_json(all fields except "signature")` with key
from `GUARDIAN_SCOPE_HMAC_KEY`. Verified via `hmac.compare_digest`.

**v1 limitation**: no DNS resolution. Targets are matched as strings, CIDRs,
or `*.domain` wildcard patterns only.

## Alternatives Considered

| Option | Rejected because |
|--------|-----------------|
| Per-tool decorators | Easy to forget on new tools; no single place to audit |
| OPA / Rego | External dependency; over-engineered for a local-first platform |
| Database-backed rules | SQLite already used for audit; coupling policy to DB adds latency and failure modes |

## Consequences

### Positive
- One place to audit: `guardian/policy/engine.py`
- Fail-closed by design
- Scope file supports time-bounded, HMAC-verified pentest scopes
- MCP-exposed tools use the same path (via `ToolExecutor`)

### Negative
- `PolicyEngine` is imported lazily inside `ToolExecutor.run()` to avoid
  circular imports; if the import fails, the tool call is denied (correct)
- Scope check has no DNS resolution (v1 limitation; document in CLI help)
