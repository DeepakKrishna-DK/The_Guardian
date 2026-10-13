# Guardian Extensions Progress

## M0 - PREFLIGHT
- [x] Branch `features/skills-tools-ai` created.
- [x] Codebase context verified (guardian/skills, tools, policy, etc).
- [x] Baseline tests passing: 524 (test_voice.py excluded due to env)

## M1 - SKILLS METADATA + POLICY WIRING
- [x] Defined Skill metadata structure (risk_tier, requires_scope, target_arg, dependencies).
- [x] Built dynamic SkillRegistry loading from `guardian/skills/library/*.md`.
- [x] Evaluated skill metadata through `PolicyEngine.evaluate()` in orchestrator.
- [x] Added `skill.request` and `skill.result` audit events.
- [x] M1 tests passing (test_m1_skills.py).

## M2 - SKILL COMPOSITION + EVAL HARNESS
- [x] Implemented `SkillTool` allowing skills to invoke other skills via `ToolExecutor`.
- [x] Enforced recursion depth limit of 5 (`skill.recursion_limit_exceeded` audit event).
- [x] Wrote fixture scenarios in `tests/skills_eval/test_skills_eval.py` using `skills_eval` marker.
- [x] M2 tests passing.

## M3 - NEW TOOLS
- [x] Added `code_exec` tool with sandboxing, timeout, and POSIX resource limits.
- [x] Added `git_read` and `git_write` tools restricted to sandbox and arg lists.
- [x] Added `network_recon` tool enforcing PolicyEngine scope rules.
- [x] Added `db_query` tool restricted to SELECT queries.
- [x] M3 tests passing (floor tests, scope, timeout, SELECT-only).

## M4 - TOOL INFRASTRUCTURE
- [x] Added `TokenBucket` rate limiter per (tool, session) in `ToolExecutor`.
- [x] Wrapped `complete` calls to record usage and cost estimates in audit log.
- [x] Added `TTLCache` in `ToolExecutor`, keyed by tool + normalized params.
- [x] Enabled opt-in `cache_ttl` for `db_query` and `network_recon`.
- [x] M4 tests passing (rate limit, cost, cache hit/bypass).

## M5 - MCP CLIENT CAPABILITY
- [x] Extended `guardian/mcp/adapter.py` to support Client mode.
- [x] Built `McpTool` to wrap discovered MCP tools.
- [x] Enforced risk_tier 2 for external tools.
- [x] M5 tests passing (tool wrapper approval check, strict import boundaries).

## M6 - AI LAYER: ROUTING & SELF-CRITIQUE
- [x] Implemented `enable_self_critique` in `GuardianCore` using `CallType.CRITIQUE` model calls to ensure it is fully advisory and audited.
- [x] Implemented Multi-model routing where `GuardianCore.process()` accepts a `CallType` and correctly routes to either cheap or strong models while preserving mock testing properties.
- [x] `swap_model` properly updates both primary/cheap models in the router.
- [x] M6 tests passing.

## M7 - AGENT EVAL HARNESS
- [x] Wrote real model-in-the-loop fixture scenarios in `tests/agent_eval/test_agent_eval.py`.
- [x] Used live `ToolLoop` integration tests targeting actual files without mocked endpoints.
- [x] Conditioned tests to dynamically skip if no real provider is available in CI.
- [x] M7 tests passing.

## M8 - STRETCH: EMBEDDING INDEX OVER CONVERSATION HISTORY
- [x] Modified `EpisodicMemory` in `guardian/memory/episodic.py` to optionally accept a `VectorStore` and `Embedder`.
- [x] Implemented vector storage into `save_turn` alongside standard SQLite records.
- [x] Updated `search` to try semantic vector similarity (`hnsw:space = cosine`) before falling back to SQLite `LIKE`.
- [x] Built test `test_m8_semantic_search_fallback` using a deterministic keyword-mapping `MockEmbedder` subclass to verify vector-store search routing.
- [x] M8 tests passing.

## HOUSEKEEPING & CI ENFORCEMENT
- [x] Verified ADR-0004 is already decided and CLOSED as ACCEPTED (SQLite + ChromaDB).
- [x] Updated `.github/workflows/ci.yml` to tighten `pip-audit` to strictly block on vulnerabilities in both `requirements-ci.txt` and the main `requirements.txt`.
- [ ] Attempted to hash-pin `requirements.txt` via `pip-compile --generate-hashes`, but BLOCKED by sandbox network timeout connecting to `pypi.org`.
- [x] All tests green (545 tests passing). CI is ready to be marked as required for merge.

## VISION I/O
- [x] Implemented `VisionLayer` in `guardian/vision/` using the same facade/lazy-load pattern as `VoiceLayer`.
- [x] Added `TransformersVisionAnalyzer` to support HuggingFace Transformers (Qwen2.5-VL and MiniCPM-V out of the box).
- [x] Added `MockVisionAnalyzer` for fast, deterministic unit testing in CI.
- [x] Exposed vision via `VisionAnalyzeTool` in `guardian/tools/vision_analyze.py` and registered it with `ToolExecutor`.
- [x] Wrote tests; suite is 100% green with 547 passing tests.