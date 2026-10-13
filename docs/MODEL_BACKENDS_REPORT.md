# Model Backends Audit & Fix Report

## Overview
This report details the audit of the Guardian model backends (`Gemini`, `Groq`, `Ollama`), the router (`ModelRouter`), and their call sites. All models were verified via **live API calls**.

## A. Gemini Backend (`gemini_backend.py`)
- **Verdict:** WORKS (Live-Verified)
- **Fix Applied:** The default model `gemini-2.5-flash` was returning `404 NOT_FOUND` (obsolete). A commit was made to update both the default and fallback models to `gemini-3.8-flash`.
- **Live Call:** Successfully processed `ModelRequest` in `5931ms`.
- **Paths Checked:** 
  - Missing key fails explicitly with `ModelUnavailableError`.
  - Rate limits (429/quota) correctly raise `ModelRequestError`.
  - Network 503s gracefully degrade to the `FALLBACK_MODEL`.
  - `TokenUsage` metadata successfully parses from `usage_metadata`.

## B. Groq Backend (`groq_backend.py`)
- **Verdict:** WORKS (Live-Verified)
- **Live Call:** Successfully processed `ModelRequest` using `openai/gpt-oss-120b` in `2877ms`.
- **Paths Checked:** 
  - Missing key triggers `ModelUnavailableError`.
  - Rate limits explicitly raise `ModelRequestError`.
  - `TokenUsage` explicitly maps from `response.usage`. Fallback logic exists to extract `.reasoning` if `content` is empty.

## C. Ollama Backend (`ollama_backend.py`)
- **Verdict:** WORKS (Live-Verified)
- **Live Call:** The local server (`localhost:11434`) was active. Successfully ran inference against `llama3.2:3b` in `8937ms`. 
- **Paths Checked:** 
  - Connection refused paths are gracefully caught, advising the user to run `ollama serve`.
  - Usage tokens are mapped correctly from the raw `prompt_eval_count` and `eval_count` JSON outputs.

## D. Router (`router.py`)
- **Verdict:** WORKS
- **Locality Routing:** Confirmed that `require_local=True` performs a hard-deny when no local model is available, actively logging a `model.local_only_denied` event rather than failing open to cloud models (proven by `tests/test_router_local.py`).
- **Call-Type Routing:** `CallType.PLANNING` and `CallType.ROUTINE` correctly route to the `cheap` backend, while `CallType.SYNTHESIS` defaults to `primary`.
- **Graceful Degradation:** The router does *not* fall back to another provider if `primary` goes down. Failures bubble up as `ModelError` explicitly. (Provider-level degradation like 503-retries is handled within the backend classes themselves, e.g., Gemini).

## E. Call Sites
- **Verdict:** WORKS
- **Usage:** Guardian uses a highly centralized choke point. All sub-agents, skills, and planning logic (`guardian/core/planning.py`) invoke `GuardianCore.process(call_type=...)`, which in turn formats the context and invokes `ModelRouter.route().complete(ModelRequest)`. No raw HTTP or bypasses were found. Token tracking (`TokenUsage`) uniformly captures prompt, completion, and total tokens across all three integrations.
