# Coding and Security Agents Recon

## Existing Components (M0 Findings)
- **Multi-Agent Architecture**: `guardian/core/agents.py` and `agents_ext.py` already define `ReconAgent`, `AnalysisAgent`, and `ResponseAgent`. I will add `CodingAgent`, `BlueTeamAgent`, `RedTeamAgent`, and `ComplianceAgent` here.
- **Compliance Attestation**: `guardian/policy/compliance.py` contains `ComplianceStore` and `ComplianceReference`. I can reuse this for the `ComplianceAgent`.
- **Techniques Library**: `guardian/techniques/library.py` contains the `TechniqueLibrary` (mapped to ATT&CK). This will be consumed by the `RedTeamAgent`.
- **Local Finetune Pipeline**: A check for `features/local-finetune` artifacts shows no existing QLoRA pipeline or saved adapters in the standard tree. I will build a minimal security-domain synthetic data + QLoRA loop.
- **Agent Eval Harness**: Exists in `tests/agent_eval/` (currently running as part of the test suite).

## What Needs to be Built Fresh
1. **CodingAgent**: Needs autonomy modes (`suggest`, `supervised`, `autonomous`), protected-paths block, and bounded iteration loop.
2. **Security Sub-Agents**: `BlueTeamAgent`, `RedTeamAgent`, `ComplianceAgent`. RedTeam requires ComplianceAgent attestation to pass.
3. **Specialist Model**: Minimal synthetic dataset generation and a QLoRA fine-tuning stub for security triage/techniques.
4. **Status Reporting**: Update `guardian status` command to reflect these new agents and modes.
