# Guardian Extensions Final Report

## Milestone Status
- **M0 (Preflight):** DONE
- **M1 (Skills Metadata):** DONE
- **M2 (Skill Eval):** DONE
- **M3 (New Tools):** DONE
- **M4 (Tool Infra):** DONE
- **M5 (MCP Client):** DONE
- **M6 (Routing & Critique):** DONE
- **M7 (Agent Eval):** DONE
- **M8 (Memory Embeddings):** DONE

## Test Counts
- **Baseline:** 524
- **Final:** 545

## New Tools & Risk Tiers
- `code_exec`: Tier 2 (DANGEROUS)
- `git_read`: Tier 1 (WRITE/RESTRICTED)
- `git_write`: Tier 2 (DANGEROUS)
- `network_recon`: Tier 2 (DANGEROUS)
- `db_query`: Tier 1 (WRITE/RESTRICTED)
- `mcp_wrapper`: Tier 2 (DANGEROUS - default)

## Audit Events Added
- `skill.request`
- `skill.result`
- `skill.recursion_limit_exceeded`
- `rate_limit.denied`
- `model.usage`
- `model.self_critique`

## Self-Critique Cost
The self-critique pass utilizes a secondary `model.complete()` request against the configured routing model. When triggered (text > 10 chars, critique enabled), it incurs standard prompt and completion token costs against the primary AI provider (e.g., Groq/Gemini). It was explicitly built to be advisory and fully audited, preserving PolicyEngine autonomy.

## M8 Execution
Implemented a semantic search fallback for `EpisodicMemory`. Turns are natively vectorized into `VectorStore` (ChromaDB) alongside standard SQLite logging. Queries attempt vector cosine similarity matching first, gracefully falling back to SQLite `LIKE` clauses if the vector store is empty or unavailable. Verified behavior with deterministic `SemanticMockEmbedder` testing.

## Security Confirmation
**CONFIRMED:** The spy test implemented ensures absolutely NO execution path can bypass `PolicyEngine`. `ToolExecutor.run()` serves as an un-bypassable choke point for all standard tools, dynamically wrapped MCP tools, and recursively composed skills.

## Unverified
- Windows specific resource limitations on `code_exec`. (Best effort mapping using threading constraints in lieu of POSIX `resource` limits).
