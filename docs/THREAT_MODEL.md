# Guardian — Threat Model v0

**Scope:** Local-first AI platform with cloud LLM backends, tool execution,
knowledge retrieval, and MCP server. Single-user desktop deployment.

---

## Assets

| Asset | Sensitivity |
|-------|-------------|
| User prompts & conversation history | High — may contain PII / credentials |
| API keys (Groq, Google) | Critical — stored in env vars |
| Audit log (`audit.db`) | High — evidence of all actions |
| Threat intelligence DB (`threats.db`) | Medium |
| Knowledge documents / ChromaDB | Medium–High (owner-determined) |
| Session memory | Medium |
| Scope file + HMAC key | High — controls pentest authorization |
| Tool execution capability (shell, file write) | Critical |

---

## Trust Boundaries

```
[User / CLI] ──────────────────┐
                               ▼
                    [GuardianCore / Orchestrator]
                         │         │
              ┌──────────┘         └──────────┐
              ▼                               ▼
   [GuardrailsLayer]              [PolicyEngine + ToolExecutor]
              │                               │
              └──────────┬────────────────────┘
                         ▼
              [ModelInterface (cloud ☁ / local)]
                    GroqBackend ──► Groq API  (internet)
                    GeminiBackend ► Google API (internet)
                         │
              [MCP Server] ◄── [External MCP Clients]
                         │
              [Storage: SQLite, ChromaDB]  (local disk / OneDrive ⚠)
```

---

## Top Threats

### T1 — Prompt Injection (via user input)
**Risk:** High  
An attacker crafts input that instructs the model to override its system
prompt, leak secrets, or invoke dangerous tools.  
**Mitigations present:** InputScanner (54 patterns) blocks before model call;
output scanner redacts secrets; one scan per request (M0 fix).  
**Gaps:** Pattern-based detection misses novel injections; no semantic
classifier; tool calls from adversarial content still reach PolicyEngine.

### T2 — Prompt Injection via Tool Output (indirect injection)
**Risk:** High  
A malicious web page or file read by a tool contains injected instructions
that the model executes in the next turn.  
**Mitigations present:** OutputScanner on model response; PolicyEngine DENY
for unknown tools; audit events logged.  
**Gaps:** Tool *output* returned to the model is not yet scanned before
re-injection (M6 stretch addresses this).

### T3 — Tool Abuse / Privilege Escalation
**Risk:** High  
The model issues a sequence of tool calls that individually appear benign
but compose into a destructive action (e.g. file read → exfiltrate via shell).  
**Mitigations present:** ToolLevel authority gate; PolicyEngine blocklist/allowlist;
scope file for network tools; approval callback for Level 1+.  
**Gaps:** No cross-turn tool-call sequence analysis; MAX_TOOL_ROUNDS=3
limits but does not eliminate chaining.

### T4 — Scope Bypass (pentest copilot)
**Risk:** High  
A manipulated scope file or missing HMAC key allows the model to target
systems outside the authorized scope.  
**Mitigations present:** Scope file with HMAC-SHA256 signature; time window
(not_before/not_after); wildcard apex exclusion; fail-closed on load error.  
**Gaps:** No DNS resolution (v1); HMAC key must be managed separately by owner.

### T5 — Exfiltration to Cloud Backends
**Risk:** Medium–High  
Sensitive data (credentials, internal IPs, security findings) in prompts
is sent to Groq/Google servers.  
**Mitigations present:** `locality` attribute on backends; audit logs provider +
model + locality (no prompt content); guardrails PII/SECRET patterns block
obvious leakage; PolicyEngine actively routes `security_guardian` and `pentest_copilot`
queries strictly to the local `OllamaBackend`.  
**Gaps:** General chat queries still route to cloud and rely solely on regex guardrails
for data loss prevention.

### T6 — Audit Log Tampering
**Risk:** Medium  
An attacker with file-system access deletes or rewrites the audit DB.  
**Mitigations present:** Hash chain detects row edits and seq gaps;
append-only triggers; `verify_chain()`.  
**Gaps:** tamper-EVIDENT not tamper-PROOF; full chain rewrite is possible;
no external anchor yet (see ADR-0001).

### T7 — Secret Leakage in Logs / Responses
**Risk:** Medium  
API keys or credentials appear in model responses, tool output, or log files.  
**Mitigations present:** OutputScanner (SECRET_LEAK group, 10 patterns);
audit payload redaction before storage; `.env` in `.gitignore`.  
**Gaps:** Guardian's own logger (guardian/logging/) writes raw text to disk;
not yet audited for secret content.

---

## Mitigations Present vs Missing

| Mitigation | Present | Missing |
|-----------|---------|---------|
| Input guardrails (54 patterns) | ✓ | Semantic/ML classifier |
| Output guardrails (secret redaction) | ✓ | Tool-output pre-injection scan |
| Policy engine (5 rules, fail-closed) | ✓ | Cross-turn sequence analysis |
| Scope file + HMAC + time window | ✓ | DNS resolution |
| Hash-chained audit log | ✓ | External hash anchor |
| Approval gate (Level 1+) | ✓ | Per-session tool limits |
| `locality` attribute on backends | ✓ | `local_only` routing enforcement |
| `.env` / `*.db` in .gitignore | ✓ | knowledge/ outside OneDrive |
| Apache-2.0 license | ✓ | — |
