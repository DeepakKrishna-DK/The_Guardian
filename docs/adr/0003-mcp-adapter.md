# ADR-0003: MCP SDK Pin and Adapter Isolation

| Field    | Value                          |
|----------|-------------------------------|
| Status   | ACCEPTED                       |
| Date     | 2026-09-22                     |
| Deciders | Project owner                  |

## Context

Guardian uses the Model Context Protocol (MCP) to expose its built-in tools
(file_read, directory, search, knowledge_query, security_audit) to external
clients. The MCP SDK evolves rapidly and has had breaking changes between
minor versions.

## Decision

1. **Pin the SDK**: `mcp==2.2.0` in `requirements.txt`. Do not upgrade without
   explicit testing and an ADR update.
2. **Adapter isolation**: `guardian/mcp/adapter.py` is the **only** module
   outside `guardian/mcp/` permitted to `import mcp`. All other code must
   use `MCPAdapter`. Enforced by `test_only_mcp_dir_imports_mcp`.
3. **Target spec revision**: `2026-07-28` (stateless, Streamable HTTP).

## Installed SDK vs Target Spec: Gap Analysis

| Feature | Target (2026-07-28) | SDK 2.2.0 | Gap |
|---------|---------------------|-----------|-----|
| Stateless servers | Required | Supported | None |
| Streamable HTTP transport | Preferred | Partial | `guardian/mcp/server.py` uses **stdio only**; HTTP not implemented |
| Roots | Deprecated | May exist | Not used in `server.py` ✓ |
| Sampling | Deprecated | May exist | Not used in `server.py` ✓ |
| Logging | Deprecated | May exist | Not used in `server.py` ✓ |
| HTTP+SSE | Deprecated | May exist | Not used in `server.py` ✓ |
| OpenTelemetry trace propagation | Added | Unknown | Not integrated yet |
| Init handshake removed | Yes | Unknown | stdio transport manages this internally |

**Verdict**: Guardian's stdio-only server is compliant with the spirit of
the 2026-07-28 spec. Streamable HTTP transport is the only meaningful gap.

## Alternatives Considered

| Option | Rejected because |
|--------|-----------------|
| Auto-upgrade mcp | Too risky; the SDK has had breaking changes without major version bumps |
| Vendor the SDK | Maintenance burden |
| Drop MCP entirely | MCP is the planned control plane for inter-module communication |

## Consequences

### Positive
- Adapter isolation means SDK upgrades require only `guardian/mcp/` changes.
- Pin prevents unexpected breakage from transitive dependency upgrades.

### Negative
- Streamable HTTP transport not implemented (v1 gap). External clients must
  use stdio or implement their own transport bridge.
- `MCPAdapter.list_tools()` and `call_tool()` currently raise
  `NotImplementedError` for remote server connections (local server uses
  stdio directly). Full remote client is deferred to a future phase.

## Owner Action Required

Decide when to implement Streamable HTTP transport. Until then, Guardian's
MCP server is usable only via stdio (local process spawning).
