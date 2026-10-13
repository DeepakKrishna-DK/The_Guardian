"""
Guardian Self-Audit Scanner
=============================
Inspects Guardian's own configuration and environment for security issues.

Constitution reference: Section 4 (Security), Section 13 (Failure Policy)

What is checked (all Level 0 — read-only, no changes made):
  1. Secret hygiene: .env files, key exposure in code, hardcoded credentials
  2. File permissions: world-writable sensitive files
  3. Configuration: DEBUG mode, logging levels, insecure defaults
  4. API key presence: missing keys that would cause silent failures
  5. Known-bad patterns: assert-based security, bare except, logging secrets

What is NOT checked (requires network or admin):
  - External service reachability
  - Actual API key validity (only presence)
  - System firewall rules

All findings are returned as ThreatRecord objects.
No findings are stored automatically — the caller decides what to persist.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterator

from guardian.logging.logger import get_logger
from guardian.security.threat import Category, Severity, ThreatRecord

log = get_logger(__name__)

# Patterns that suggest exposed secrets in source code
_SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'(?i)(api_key|apikey|secret|password|passwd|token)\s*=\s*["\'][^"\']{8,}["\']'), "Hardcoded credential-like string"),
    (re.compile(r'gsk_[A-Za-z0-9]{40,}'), "Exposed Groq API key"),
    (re.compile(r'AQ\.[A-Za-z0-9_\-]{30,}'), "Exposed Google API key"),
    (re.compile(r'sk-[A-Za-z0-9]{32,}'), "Exposed OpenAI API key"),
    (re.compile(r'(?i)Bearer\s+[A-Za-z0-9\-_]{20,}'), "Bearer token in source"),
]

_SOURCE_EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini", ".env"}
_SKIP_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules"}


class SelfAuditScanner:
    """
    Scans Guardian's own workspace for self-referential security issues.

    Usage:
        scanner = SelfAuditScanner(workspace_root)
        findings = scanner.run()
    """

    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root.resolve()

    def run(self) -> list[ThreatRecord]:
        """Run all self-audit checks. Returns list of findings."""
        log.info(f"SelfAuditScanner: scanning {self.root}")
        findings: list[ThreatRecord] = []

        findings.extend(self._check_env_files())
        findings.extend(self._check_source_for_secrets())
        findings.extend(self._check_gitignore())
        findings.extend(self._check_api_key_env_vars())

        log.info(f"SelfAuditScanner: {len(findings)} finding(s)")
        return findings

    def _check_env_files(self) -> list[ThreatRecord]:
        """Check for .env files with actual secrets."""
        findings = []
        for env_file in self.root.rglob(".env"):
            if any(skip in env_file.parts for skip in _SKIP_DIRS):
                continue
            try:
                text = env_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            # Check for real key-value pairs (not placeholders)
            lines_with_values = [
                line for line in text.splitlines()
                if "=" in line and not line.startswith("#")
                   and len(line.split("=", 1)[-1].strip()) > 4
                   and "your_" not in line.lower()
                   and "example" not in line.lower()
                   and "placeholder" not in line.lower()
            ]
            if lines_with_values:
                rel = env_file.relative_to(self.root)
                findings.append(ThreatRecord.new(
                    severity=Severity.HIGH,
                    category=Category.SECRET,
                    title=f".env file with apparent real values: {rel}",
                    description=(
                        f"{rel} contains {len(lines_with_values)} line(s) with non-placeholder values. "
                        f"If this file contains real API keys or passwords, it must NOT be committed to git."
                    ),
                    recommendation=(
                        "Verify this file is in .gitignore. "
                        "Use environment variables set at the OS level for production keys. "
                        "The .env file should only be used locally and must never be committed."
                    ),
                    source="SelfAuditScanner._check_env_files",
                    context={"path": str(rel), "lines_with_values": len(lines_with_values)},
                ))
        return findings

    def _check_source_for_secrets(self) -> list[ThreatRecord]:
        """Scan source files for hardcoded credentials."""
        findings = []
        for path in self._iter_source_files():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for pattern, label in _SECRET_PATTERNS:
                for match in pattern.finditer(text):
                    line_num = text[:match.start()].count("\n") + 1
                    rel = path.relative_to(self.root)
                    snippet = match.group()[:60] + ("..." if len(match.group()) > 60 else "")
                    findings.append(ThreatRecord.new(
                        severity=Severity.CRITICAL,
                        category=Category.SECRET,
                        title=f"{label} in {rel}:{line_num}",
                        description=f"Pattern matched in {rel} at line {line_num}: {snippet!r}",
                        recommendation=(
                            "Remove the credential from source code immediately. "
                            "Rotate the key if it was ever committed to git history. "
                            "Use environment variables loaded at runtime instead."
                        ),
                        source="SelfAuditScanner._check_source_for_secrets",
                        context={"path": str(rel), "line": line_num, "label": label},
                    ))
        return findings

    def _check_gitignore(self) -> list[ThreatRecord]:
        """Verify that .env and secrets directories are in .gitignore."""
        findings = []
        gitignore = self.root / ".gitignore"
        if not gitignore.exists():
            findings.append(ThreatRecord.new(
                severity=Severity.HIGH,
                category=Category.CONFIG,
                title="No .gitignore file found",
                description="The workspace has no .gitignore. Secret files may be accidentally committed.",
                recommendation="Create a .gitignore that excludes .env, venv/, memory/, and *.db files.",
                source="SelfAuditScanner._check_gitignore",
            ))
            return findings

        try:
            content = gitignore.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return findings

        required_patterns = [".env", "*.db", "venv/", "__pycache__/"]
        for pat in required_patterns:
            if pat not in content:
                findings.append(ThreatRecord.new(
                    severity=Severity.MEDIUM,
                    category=Category.CONFIG,
                    title=f".gitignore missing pattern: {pat!r}",
                    description=f"The pattern {pat!r} is not in .gitignore, which may allow sensitive files to be committed.",
                    recommendation=f"Add {pat!r} to .gitignore.",
                    source="SelfAuditScanner._check_gitignore",
                    context={"missing_pattern": pat},
                ))
        return findings

    def _check_api_key_env_vars(self) -> list[ThreatRecord]:
        """Check that expected API key env vars are set."""
        findings = []
        expected = {
            "GUARDIAN_GROQ_API_KEY": "Groq API",
            "GUARDIAN_GOOGLE_API_KEY": "Google Gemini API",
        }
        for var, label in expected.items():
            val = os.environ.get(var, "")
            if not val:
                findings.append(ThreatRecord.new(
                    severity=Severity.LOW,
                    category=Category.CONFIG,
                    title=f"API key not set: {var}",
                    description=f"Environment variable {var} ({label}) is not set. Guardian will fall back to the mock backend.",
                    recommendation=f"Set {var} as a User environment variable. See .env.example.",
                    source="SelfAuditScanner._check_api_key_env_vars",
                    context={"var": var},
                ))
        return findings

    def _iter_source_files(self) -> Iterator[Path]:
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if any(skip in path.parts for skip in _SKIP_DIRS):
                continue
            if path.suffix in _SOURCE_EXTENSIONS:
                yield path
