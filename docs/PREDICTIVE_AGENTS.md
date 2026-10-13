# Predictive Agents (M0 Recon)

## Reconnaissance Findings

*   **Technique Library**: Yes, a technique library exists in `guardian/techniques/library.py` (added in the Cognitive Pass).
*   **Episodic/Proficiency Tracking**: Yes, execution memory and proficiency tracking exist in `guardian/memory/execution.py` (added in the Cognitive Pass).
*   **CVE Scanning Output**: There is no actual CVE scanning functionality in the codebase. The `guardian/security/scanner.py` only performs environment checks (processes, listening ports, sensitive files).
*   **Drift from Context**:
    *   `guardian/pentest/` directory does not exist. The pentest copilot is implemented as a skill in `guardian/skills/library/pentest_copilot.md`.
    *   CVE scanning was listed as Phase 6 context, but it is entirely missing from the codebase. The `ThreatRecord` schema exists but it has no fields for CVE IDs or EPSS scores.

## Implementation Plan
*   **M1**: Will add an `epss_score` field to `ThreatRecord` (or `context` dict) and implement a basic CVE parsing from the threat title/context to query the FIRST.org EPSS API, or introduce a mock CVE scanner to demonstrate EPSS fetching. Since there is no CVE scanning, I will add an explicit EPSS lookup function that can be used by the `AnalysisAgent` or added to the `EnvironmentScanner` as a mock.

## EPSS API Verification
Verified the current FIRST.org EPSS API via web search:
- Endpoint format: `https://api.first.org/data/v1/epss?cve={cve_id}` (also supports comma-separated list)
- Authentication: None required. Public API.
- Rate limits: 1,000 requests per minute. Returns HTTP 429 if exceeded.

## Dependencies
- Verified `scikit-learn` is already installed. Version 1.9.1. License: BSD-3-Clause.
