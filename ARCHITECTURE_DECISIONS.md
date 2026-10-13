# ARCHITECTURE_DECISIONS.md
# AI Guardian — Architecture Decision Record
# Version: 0.1 (Phase 0 — Initial)
# Date: 2026-09-18

---

## ADR-001: Constitution as Primary Specification

**Decision**: GUARDIAN_CONSTITUTION_v0.1.md is the authoritative governing specification for all design and implementation decisions.

**Rationale**: Establishes a stable, version-controlled contract that prevents scope creep and unauthorized changes.

**Constraints**:
- Any implementation that conflicts with the Constitution must STOP and report the conflict.
- Amendments to the Constitution require explicit user approval.
- Architecture Decisions that contradict the Constitution are invalid.

**Status**: ACTIVE

---

## ADR-002: Model Independence (Replaceable AI Backend)

**Decision**: Guardian must never be permanently coupled to one AI model or provider.

**Rationale**: Constitution §10 requires a model adapter/interface layer. The underlying AI can change (local → external → upgraded local) without redesigning the rest of the system.

**Constraints**:
- All AI interaction goes through a `ModelInterface` abstraction.
- No component may directly call a model API without going through this interface.
- Initial model selection must be based on verified hardware capability, not assumptions.

**Status**: ACTIVE — interface to be designed in Phase 2

---

## ADR-003: Hardware Constraints

**Decision**: Architectural decisions must respect the current hardware.

**Observed hardware** (Phase 0):
- CPU: AMD Ryzen 7 7435HS — 8 cores / 16 threads / 3100 MHz base
- RAM: 16 GB DDR5
- GPU: NVIDIA RTX 3050 Laptop — 4 GB VRAM
- No NPU detected or assumed
- PyTorch: currently CPU-only (GPU-enabled PyTorch not yet installed)

**Constraints**:
- Do not assume GPU acceleration is available until CUDA PyTorch is installed and verified.
- 4 GB VRAM is a tight constraint for local LLM inference. Models must be selected accordingly.
- Do not assume a model will run acceptably until benchmarked on this machine.

**Status**: ACTIVE

---

## ADR-004: Security and Permission Model

**Decision**: Guardian implements a three-level authority model as specified in Constitution §3.

| Level | Name | Approval Required |
|-------|------|-------------------|
| 0 | Observe | Automatic |
| 1 | Create / Experiment | Automatic within designated workspaces |
| 2 | Consequential Action | Explicit user approval required |

**Constraints**:
- Guardian must never bypass Level 2 approval gates.
- Security testing is only permitted against systems the user owns or is explicitly authorized to assess.
- Guardian must not be given unrestricted permission to modify its own trusted core.

**Status**: ACTIVE

---

## ADR-005: No NPU Assumed

**Decision**: No NPU is assumed to exist on the development machine.

**Rationale**: Phase 0 inspection found no NPU. The ASUS TUF A15 with Ryzen 7 7435HS does not have a confirmed NPU in inspection results.

**Constraints**:
- No NPU-specific code paths shall be added without hardware verification.
- Future NPU support can be added via the model interface abstraction if hardware is confirmed.

**Status**: ACTIVE

---

## ADR-006: Incremental Development — No Phase Skipping

**Decision**: Development proceeds strictly phase-by-phase. No phase begins until the prior phase has passed verification.

**Phase sequence**:
0. Repository Inspection → (current)
1. Project Foundation
2. Model Abstraction
3. Core Orchestrator
4. Memory
5. Skill System
6. Security Layer
7. Tool System
8. Testing + Evaluation
9+ Future (Voice, Vision, RAG, Autonomy, etc.)

**Constraints**:
- A smaller verified system is preferred over a large unverified system.
- If a component fails verification, it must be fixed before proceeding.

**Status**: ACTIVE

---

## ADR-007: Virtual Environment Isolation

**Decision**: Guardian development will use a dedicated Python virtual environment.

**Rationale**:
- The global Python environment has 100+ packages installed.
- A dedicated venv prevents dependency conflicts and makes Guardian reproducible.
- Allows Guardian's dependencies to be pinned separately.

**Constraints**:
- The venv must be created inside the Guardian project directory.
- Guardian must not modify global Python packages.

**Status**: PENDING — to be created in Phase 1

---

## ADR-008: Git Version Control Required

**Decision**: All Guardian source code must be version-controlled with Git.

**Rationale**: Enables reversible changes, audit history, and safe experimentation.

**Current state**: Git is NOT installed (Phase 0 finding). Must be installed before Phase 1 code is written.

**Constraints**:
- Git installation is a prerequisite for Phase 1.
- Installation requires user awareness (Level 2 action if classified as system modification).

**Status**: PENDING — Git installation required

---

## ADR-009: Workspace Boundary

**Decision**: Guardian project files are confined to `C:\Users\dk-32\OneDrive\Desktop\Guardian\` during development.

**Rationale**: Provides a clear, safe boundary for Level 1 operations.

**Constraints**:
- Guardian may not write files outside this directory without explicit user approval.
- The `hylexcrypt` project at `C:\Users\dk-32\OneDrive\Desktop\v2050.1.0\` must not be modified.

**Status**: ACTIVE

---

## ADR-010: Python Version Risk Acknowledgment

**Decision**: Python 3.14.2 is the current runtime. Its newness is acknowledged as a risk.

**Rationale**: Python 3.14 was released December 2025. Some packages may not fully support it. This must be monitored.

**Mitigation**:
- Test each new dependency before committing to it.
- Prefer packages with confirmed 3.14 compatibility.
- Document any compatibility issues in PROJECT_STATE.md.

**Status**: ACTIVE — monitoring required

---

## Open Questions (not yet decided)

These require more information before a decision can be made:

1. **First AI model**: What model will serve as the initial AI backend? Options include Groq API, Google Gemini API (both SDKs already installed), Ollama (not installed), or HuggingFace local. Decision deferred to Phase 2 after hardware capability is verified.

2. **CUDA PyTorch**: Should a CUDA-enabled PyTorch be installed? This would enable GPU inference but requires careful version matching. UNVERIFIED: Python 3.14 + CUDA PyTorch compatibility.

3. **Git installation method**: Via Chocolatey (already installed), manual installer, or winget? To be decided with user in Phase 1.

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-18 | Initial document — Phase 0 findings |

---
*This document is updated as architectural decisions are made.*
*All decisions reference the GUARDIAN_CONSTITUTION_v0.1.md as the governing specification.*
