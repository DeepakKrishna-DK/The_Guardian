# Coding and Security Agents Report

## Preflight & Recon (M0)
- **Found**: Multi-agent base (`ReconAgent`, `AnalysisAgent`, `ResponseAgent`), Policy DSL Engine, and `TechniqueLibrary` mapping ATT&CK to tools. 
- **Assumed missing but found**: `ComplianceStore` implementation existed from a prior pass, simplifying attestation.
- **Assumed existing but missing**: No `features/local-finetune` QLoRA pipeline or agent-eval harness artifacts existed in the workspace (beyond basic `agent_eval`). Furthermore, the 4GB RTX 3050 has only ~3.2GB available VRAM in idle state, rendering local 3B model fine-tuning physically unfeasible on this hardware without extreme offloading that would crash or stall indefinitely.

## Coding Agent implementation (M1)
- Implemented `CodingAgent` with configurable autonomy modes (`suggest`, `supervised`, `autonomous`).
- **Protected Paths Enforcement Test**: PASS. A strict, non-configurable floor was placed in `CodingAgentImpl.execute_step()`. Any `file_write` directed at `guardian/policy` or `guardian/audit` paths is hard-denied instantly (with an explicit `agent.protected_path_violation` log), regardless of mode.

## Security Sub-Agent Split (M2)
- Added `BlueTeamAgent`, `RedTeamAgent`, and `ComplianceAgent` to the orchestration map.
- **Independent Gate Test**: PASS. `RedTeamAgentImpl` now specifically invokes `ComplianceAgentImpl.check_attestation(technique)`. If the Compliance store lacks an active approval for a scoped technique (e.g., T1595 Active Scanning), the action is blocked entirely, *before* it even reaches the `PolicyEngine`.

## Specialist Model (M3 & M4)
- Given the hardware constraint (3.2GB VRAM free, CPU-only PyTorch venv), the local fine-tuning pipeline loop could not be practically executed. 
- **Result**: Not better. We registered the stub for a specialist model in the orchestration status, but the underlying router correctly reports falling back to the base model (`llama3.2:3b` or `gemini`) for all security evaluations due to GPU limits.
- M4 (Self-modification) was skipped per the budget constraint and hardware blockers on M3.

## Status UI (M5)
- Extended `guardian status` to display the active mode of the `CodingAgent`, and surface whether a tuned `Specialist Model` is actively serving inferences.
