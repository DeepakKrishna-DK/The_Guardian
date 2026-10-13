"""
Guardian Environment Scanner
==============================
Observes the local environment for suspicious activity.
ALL operations are Level 0 (read-only — no modifications made).

Constitution reference: Section 4 (Security), Section 3.L0 (Observe)

Checks (read-only, no admin rights required):
  1. Running processes — look for known suspicious names or anomalies
  2. Open network ports (listening) — detect unexpected listeners
  3. Sensitive file existence — check for common credential files in wrong places

What this is NOT:
  - Not a full AV/EDR replacement
  - Not an intrusion detection system
  - Cannot inspect process memory or intercept network traffic (no admin needed)
  - Cannot block anything (observation only per Constitution L0)

All findings returned as ThreatRecord objects.
"""

from __future__ import annotations

import socket
from pathlib import Path

from guardian.logging.logger import get_logger
from guardian.security.threat import Category, Severity, ThreatRecord

log = get_logger(__name__)

# Process names that may indicate security tools or malware
# (flagged as INFO — not necessarily malicious, just notable)
_NOTABLE_PROCESSES: set[str] = {
    "wireshark", "tcpdump", "nmap", "netcat", "nc",
    "metasploit", "msfconsole", "burpsuite", "zaproxy",
    "mimikatz", "procdump", "psexec",
}

# Ports that are notable if open on localhost
_NOTABLE_PORTS: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    3389: "RDP",
    5900: "VNC",
    6379: "Redis (unauthenticated default)",
    27017: "MongoDB (unauthenticated default)",
    5432: "PostgreSQL",
    3306: "MySQL",
    8080: "HTTP alt (possible proxy/web server)",
    8443: "HTTPS alt",
}

# Sensitive files that should not exist in user home or common locations
_SENSITIVE_FILE_PATTERNS: list[tuple[str, str]] = [
    ("*.pem",   "PEM certificate/key file"),
    ("*.key",   "Private key file"),
    ("id_rsa",  "SSH private key"),
    ("id_ecdsa","SSH private key (ECDSA)"),
    ("*.pfx",   "PKCS12 certificate bundle"),
]


class EnvironmentScanner:
    """
    Read-only scanner for local environment anomalies.

    Usage:
        scanner = EnvironmentScanner(workspace_root)
        findings = scanner.run()
    """

    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root.resolve()

    def run(self) -> list[ThreatRecord]:
        """Run all environment checks. Returns findings list."""
        log.info("EnvironmentScanner: starting")
        findings: list[ThreatRecord] = []

        findings.extend(self._check_processes())
        findings.extend(self._check_listening_ports())
        findings.extend(self._check_sensitive_files_in_workspace())
        findings.extend(self._check_cves())

        log.info(f"EnvironmentScanner: {len(findings)} finding(s)")
        return findings

    def _check_cves(self) -> list[ThreatRecord]:
        """Mock CVE check to demonstrate EPSS integration."""
        findings = []
        # Mock finding a vulnerable dependency in requirements.txt
        req_file = self.root / "requirements.txt"
        if req_file.exists():
            # Pretend we found CVE-2022-22965
            from guardian.security.epss import EPSSClient
            epss_client = EPSSClient()
            score = epss_client.get_score("CVE-2022-22965")
            
            rec = ThreatRecord.new(
                severity=Severity.HIGH,
                category=Category.GENERAL,
                title="Spring4Shell Vulnerability (CVE-2022-22965)",
                description="Mock finding of Spring Framework RCE vulnerability.",
                recommendation="Update Spring Framework to a patched version.",
                source="EnvironmentScanner"
            )
            rec.context = {"cve_id": "CVE-2022-22965", "epss_score": score}
            findings.append(rec)
        return findings

    def _check_processes(self) -> list[ThreatRecord]:
        """Check running processes for notable names."""
        findings = []
        try:
            import psutil
            procs = [(p.pid, p.name().lower()) for p in psutil.process_iter(["pid", "name"])]
        except Exception as exc:
            log.warning(f"Process scan failed: {exc}")
            return []

        for pid, name in procs:
            base = name.replace(".exe", "").lower()
            if base in _NOTABLE_PROCESSES:
                findings.append(ThreatRecord.new(
                    severity=Severity.INFO,
                    category=Category.PROCESS,
                    title=f"Notable process running: {name} (PID {pid})",
                    description=(
                        f"Process '{name}' (PID {pid}) is running. "
                        f"This may be a security tool, network analyzer, or penetration testing tool."
                    ),
                    recommendation="Verify this process is expected. If not, investigate.",
                    source="EnvironmentScanner._check_processes",
                    context={"pid": pid, "name": name},
                ))
        return findings

    def _check_listening_ports(self) -> list[ThreatRecord]:
        """Check for notable open listening ports on localhost."""
        findings = []
        open_notable: list[int] = []

        for port, service in _NOTABLE_PORTS.items():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.3)
                    result = sock.connect_ex(("127.0.0.1", port))
                    if result == 0:
                        open_notable.append(port)
                        sev = Severity.HIGH if port in (23, 3389, 5900) else Severity.INFO
                        findings.append(ThreatRecord.new(
                            severity=sev,
                            category=Category.NETWORK,
                            title=f"Port {port} ({service}) open on localhost",
                            description=f"Port {port} ({service}) is accepting connections on 127.0.0.1.",
                            recommendation=(
                                f"Verify {service} on port {port} is intentional. "
                                f"If not needed, disable the service."
                            ),
                            source="EnvironmentScanner._check_listening_ports",
                            context={"port": port, "service": service},
                        ))
            except Exception:
                pass  # Timeout or error = port not open

        return findings

    def _check_sensitive_files_in_workspace(self) -> list[ThreatRecord]:
        """Look for private key / certificate files within the workspace."""
        findings = []
        skip = {".git", "venv", "__pycache__"}

        for pattern, label in _SENSITIVE_FILE_PATTERNS:
            for fpath in self.root.rglob(pattern):
                if any(s in fpath.parts for s in skip):
                    continue
                rel = fpath.relative_to(self.root)
                findings.append(ThreatRecord.new(
                    severity=Severity.MEDIUM,
                    category=Category.SECRET,
                    title=f"{label} found in workspace: {rel}",
                    description=f"File {rel} appears to be a sensitive credential or key file.",
                    recommendation=(
                        "Verify this file is intentional and needed. "
                        "Ensure it is in .gitignore and never committed to git. "
                        "Store private keys in a dedicated secrets manager if possible."
                    ),
                    source="EnvironmentScanner._check_sensitive_files_in_workspace",
                    context={"path": str(rel)},
                ))
        return findings
