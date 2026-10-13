# Cognitive Pass Reconnaissance

- **Self-critique**: Exists in `guardian/core/orchestrator.py` as an advisory post-generation check (if `enable_self_critique=True`). It critiques the full text output after it is generated. It doesn't yet do a whole-plan review *before* execution.
- **Agent Eval Scenarios**: `tests/agent_eval/test_agent_eval.py` exists! It contains two tests (`test_agent_eval_synthesis_capabilities` and `test_agent_eval_tool_call_routing`).
- **Skill metadata**: Skills are likely updated from the previous `features/skills-tools-ai` pass, holding metadata like `name`, `description`, `risk_tier`, `requires_scope`, etc.
- **Conversation Memory Schema**: Found in `guardian/memory/episodic.py`. The `EpisodicRecord` saves `user_message` and `assistant_reply` (raw content). We must NOT save raw content for the new cognitive/proficiency episodic memory, so we will need a new table in the same store, e.g. `execution_outcomes`, which logs metadata only (success/failure, duration, risk flags raised, timestamp).
- **Pentest module**: Currently `guardian/pentest/` doesn't exist as a top-level directory. The copilot logic must live in skills or tools (`guardian/tools/network_recon.py`).

We will implement M1 next.

## M2 - Technique Library
- **MITRE ATT&CK® License Verification**: Queried the official license terms via `search_web`. The MITRE Corporation grants a non-exclusive, royalty-free license for research, development, and commercial use. It requires attribution (e.g. citing "MITRE ATT&CK®" on first reference) and the copyright designation. The dataset will be a small curated subset strictly mapping to Guardian's existing tools/skills.

## M1 - Planning + Self-Verification
- Added `guardian/core/planning.py` with `Planner` class to produce explicit JSON plans mapping steps to tools, tools rationale, and confidence scores.
- Implemented `verify_plan` that iterates over plan steps and runs `PolicyEngine.evaluate()` before execution. Warnings are recorded without blocking the actual execution plan strictly, and audited.

## M3 - Procedures
- Added `guardian/core/procedure.py` with `ProcedureRunner` that executes a sequence of named steps.
- Each step goes through `PolicyEngine.evaluate()` explicitly before being dispatched to `ToolExecutor.run()`. Steps requiring approval will halt and request user confirmation.

## M4 - Episodic Memory and Proficiency
- Added `ExecutionMemory` to `guardian/memory/execution.py` to record tool/skill execution outcomes (metadata-only: success/failure, duration, risk flags).
- Implemented `compute_proficiency` to generate a decaying score based on the outcome history (half-life decay).

## M5 - Judgment Eval Scenarios
- Added `tests/agent_eval/test_cognitive_judgments.py` containing `test_judgment_out_of_scope` and `test_judgment_safe_action`.
- Validated that the out-of-scope scenario correctly raises a `PolicyEngine` flag (or results in a refusal), while the safe scenario passes without warnings.

## M6 - Surface It
- Modified `guardian/core/status.py` and `guardian/cli.py` to query `ExecutionMemory` for total execution outcomes and proficiency metrics for top tools (network_recon, file_read, shell).
- Exposed the `Cognitive Layer` section under `guardian status`.

## M7 - Semantic Episodic Retrieval (Stretch)
- Wired ChromaDB embedding into `ExecutionMemory.save_outcome`. If a `vector_store` and `embedder` are provided during instantiation, it seamlessly embeds a 1-sentence summary of the outcome for semantic retrieval.
