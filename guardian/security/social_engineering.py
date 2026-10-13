"""
Guardian Social Engineering Defense System (SET-Inspired)
==========================================================
Defends against social engineering vectors modeled after TrustedSec's
Social-Engineer Toolkit (SET):
  1. Spear-Phishing Attack Vectors (pretexting, emotional coercion, impersonation)
  2. Web & Credential Harvester Vectors (cloned sites, typo-squatting, DGA)
  3. Infectious Media & Weaponized Attachments (extension cloaking, LNK, HTA)
  4. Encoded Payload Vectors (PowerShell -enc, execution download cradles)

Provides deep heuristic analysis, MITRE ATT&CK / SET vector mapping,
and defensive remediation recommendations.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse


class RiskTier(str, Enum):
    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ThreatIndicator:
    category: str
    vector: str
    description: str
    severity: float  # 0.0 to 1.0
    evidence: str


@dataclass
class SocialEngineeringReport:
    text_length: int
    risk_score: float  # 0.0 to 1.0
    risk_tier: RiskTier
    indicators: list[ThreatIndicator] = field(default_factory=list)
    detected_vectors: list[str] = field(default_factory=list)
    urls_analyzed: list[dict[str, Any]] = field(default_factory=list)
    psychological_triggers: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def is_malicious(self) -> bool:
        return self.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL)

    def summary(self) -> str:
        ind_summary = "; ".join(f"{i.category}: {i.description}" for i in self.indicators[:3])
        return (
            f"Risk Tier: {self.risk_tier.value} (Score: {self.risk_score:.2f}) | "
            f"Vectors: {', '.join(self.detected_vectors) or 'None'} | "
            f"Indicators: {len(self.indicators)} [{ind_summary}]"
        )


class SocialEngineeringDetector:
    """
    Production-grade detector analyzing communications for social engineering tactics.
    """

    # Pretexting keywords & psychological manipulation patterns
    URGENCY_PATTERNS = [
        r"\b(urgent|immediately|immediate action|within \d+ (hours?|minutes?)|right now|asap)\b",
        r"\b(suspended|termination|disabled|locked out|restricted immediately)\b",
        r"\b(act fast|final warning|last notice|time[- ]sensitive)\b",
    ]

    AUTHORITY_PATTERNS = [
        r"\b(it support|it department|helpdesk|system administrator|security operations)\b",
        r"\b(ceo|cfo|executive office|director of finance|legal team|compliance officer)\b",
        r"\b(internal revenue service|irs|fbi|law enforcement|federal court|hr department)\b",
        r"\b(microsoft support|google security team|apple security|bank security)\b",
    ]

    FEAR_COERCION_PATTERNS = [
        r"\b(legal action|lawsuit|prosecution|arrest warrant|police report)\b",
        r"\b(unauthorized access detected|security breach|account compromised)\b",
        r"\b(pay penalty|fine of|face consequences|dismissal)\b",
    ]

    RECIPROCATION_GREED_PATTERNS = [
        r"\b(wire transfer|fund transfer|direct deposit|payroll update)\b",
        r"\b(refund voucher|unclaimed prize|lottery|crypto grant|exclusive gift)\b",
        r"\b(invoice attached|pending payment|invoice #[0-9a-z-]+)\b",
    ]

    # Credential harvesting & fake login patterns
    CREDENTIAL_PATTERNS = [
        r"\b(re-enter your password|verify credentials|confirm your password|login details)\b",
        r"\b(update payment details|card verification|ssn required|social security)\b",
        r"\b(sync your account|validate identity|authentication required to proceed)\b",
    ]

    # Cloaked & weaponized attachment patterns (SET Infectious Media / Attachment)
    DANGEROUS_EXTENSIONS = [
        r"\b\w+\.pdf\.exe\b",
        r"\b\w+\.docx?\.exe\b",
        r"\b\w+\.xlsx?\.vbs\b",
        r"\b\w+\.(hta|scr|iso|vbs|wsf|bat|cmd|ps1|lnk)\b",
    ]

    # Encoded PowerShell cradles (SET PowerShell Attack Vector)
    POWERSHELL_PAYLOAD_PATTERNS = [
        r"powershell(\.exe)?\s+(-(enc|encodedcommand|e))\s+[a-za-z0-9+/=]{16,}",
        r"powershell.*(-nop|-noprofile|-w\s+hidden|-windowstyle\s+hidden)",
        r"(downloadstring|downloaddata|downloadfile)\s*\(",
        r"iex\s*\(|\biex\s+new-object\b",
    ]

    # Trusted brand targets often spoofed in SET site cloner
    BRAND_TARGETS = [
        "microsoft", "office365", "google", "paypal", "apple", "amazon",
        "chase", "wellsfargo", "bankofamerica", "netflix", "dropbox", "docusign",
    ]

    def __init__(self):
        pass

    def analyze(self, text: str) -> SocialEngineeringReport:
        if not text:
            return SocialEngineeringReport(
                text_length=0,
                risk_score=0.0,
                risk_tier=RiskTier.SAFE,
                recommendations=["Input text is empty."],
            )

        indicators: list[ThreatIndicator] = []
        vectors = set()
        triggers = set()

        text_lower = text.lower()

        # 1. Psychological & Pretexting Trigger Analysis
        # Urgency
        for pat in self.URGENCY_PATTERNS:
            m = re.search(pat, text_lower)
            if m:
                triggers.add("URGENCY")
                indicators.append(ThreatIndicator(
                    category="PRETEXTING",
                    vector="SET_SPEAR_PHISHING",
                    description="Urgency/pressure language designed to bypass critical evaluation",
                    severity=0.55,
                    evidence=m.group(0),
                ))
                vectors.add("SET_SPEAR_PHISHING")
                break

        # Authority
        for pat in self.AUTHORITY_PATTERNS:
            m = re.search(pat, text_lower)
            if m:
                triggers.add("AUTHORITY_IMPERSONATION")
                indicators.append(ThreatIndicator(
                    category="IMPERSONATION",
                    vector="SET_SPEAR_PHISHING",
                    description="Authority or corporate entity impersonation",
                    severity=0.65,
                    evidence=m.group(0),
                ))
                vectors.add("SET_SPEAR_PHISHING")
                break

        # Fear / Coercion
        for pat in self.FEAR_COERCION_PATTERNS:
            m = re.search(pat, text_lower)
            if m:
                triggers.add("FEAR_COERCION")
                indicators.append(ThreatIndicator(
                    category="COERCION",
                    vector="SET_SPEAR_PHISHING",
                    description="Intimidation or fear-inducing consequence claims",
                    severity=0.70,
                    evidence=m.group(0),
                ))
                vectors.add("SET_SPEAR_PHISHING")
                break

        # Greed / Invoice / Financial lure
        for pat in self.RECIPROCATION_GREED_PATTERNS:
            m = re.search(pat, text_lower)
            if m:
                triggers.add("FINANCIAL_LURE")
                indicators.append(ThreatIndicator(
                    category="FINANCIAL_LURE",
                    vector="SET_MASS_MAILER",
                    description="Financial or payment bait",
                    severity=0.50,
                    evidence=m.group(0),
                ))
                vectors.add("SET_MASS_MAILER")
                break

        # Credential solicitation
        for pat in self.CREDENTIAL_PATTERNS:
            m = re.search(pat, text_lower)
            if m:
                indicators.append(ThreatIndicator(
                    category="CREDENTIAL_HARVESTING",
                    vector="SET_CREDENTIAL_HARVESTER",
                    description="Explicit credential or sensitive data solicitation",
                    severity=0.85,
                    evidence=m.group(0),
                ))
                vectors.add("SET_CREDENTIAL_HARVESTER")
                break

        # 2. URL & Credential Harvester Analysis (SET Web Vectors)
        urls_analyzed = []
        url_matches = re.findall(r"https?://[^\s<>\"']+", text, re.IGNORECASE)
        for u in url_matches:
            url_info = self._analyze_url(u)
            urls_analyzed.append(url_info)
            if url_info["is_suspicious"]:
                indicators.append(ThreatIndicator(
                    category="SUSPICIOUS_URL",
                    vector="SET_CREDENTIAL_HARVESTER",
                    description=f"Suspicious URL: {url_info['reason']}",
                    severity=url_info["severity"],
                    evidence=u,
                ))
                vectors.add("SET_CREDENTIAL_HARVESTER")

        # 3. Weaponized Attachments & Infectious Media (SET Payload)
        for pat in self.DANGEROUS_EXTENSIONS:
            m = re.search(pat, text_lower)
            if m:
                indicators.append(ThreatIndicator(
                    category="WEAPONIZED_ATTACHMENT",
                    vector="SET_INFECTIOUS_MEDIA",
                    description=f"Dangerous executable/script attachment indicator: {m.group(0)}",
                    severity=0.90,
                    evidence=m.group(0),
                ))
                vectors.add("SET_INFECTIOUS_MEDIA")

        # 4. Encoded PowerShell & Command Injection (SET PowerShell Vectors)
        for pat in self.POWERSHELL_PAYLOAD_PATTERNS:
            m = re.search(pat, text_lower)
            if m:
                indicators.append(ThreatIndicator(
                    category="PAYLOAD_EXECUTION",
                    vector="SET_POWERSHELL_PAYLOAD",
                    description="Obfuscated or encoded PowerShell cradle detected",
                    severity=0.95,
                    evidence=m.group(0),
                ))
                vectors.add("SET_POWERSHELL_PAYLOAD")

        # Calculate composite risk score
        if not indicators:
            risk_score = 0.05 if len(text) > 0 else 0.0
            risk_tier = RiskTier.SAFE
        else:
            # Weighted diminishing summation
            max_sev = max(i.severity for i in indicators)
            bonus = min(0.40, (len(indicators) - 1) * 0.10)
            risk_score = min(1.0, max_sev + bonus)

            if risk_score >= 0.80:
                risk_tier = RiskTier.CRITICAL
            elif risk_score >= 0.60:
                risk_tier = RiskTier.HIGH
            elif risk_score >= 0.35:
                risk_tier = RiskTier.MEDIUM
            else:
                risk_tier = RiskTier.LOW

        # Generate actionable defense recommendations
        recommendations = self._generate_recommendations(indicators, vectors, urls_analyzed)

        return SocialEngineeringReport(
            text_length=len(text),
            risk_score=round(risk_score, 2),
            risk_tier=risk_tier,
            indicators=indicators,
            detected_vectors=sorted(list(vectors)),
            urls_analyzed=urls_analyzed,
            psychological_triggers=sorted(list(triggers)),
            recommendations=recommendations,
        )

    def _analyze_url(self, url: str) -> dict[str, Any]:
        """Analyze a URL for phishing, typo-squatting, IP hosting, and credential harvesting."""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower().split(":")[0]
            path = parsed.path.lower()
        except Exception:
            return {
                "url": url,
                "is_suspicious": True,
                "severity": 0.60,
                "reason": "Malformed URL syntax",
            }

        # 1. IP address in host
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host):
            return {
                "url": url,
                "is_suspicious": True,
                "severity": 0.85,
                "reason": "Direct IP address host used instead of legitimate domain",
            }

        # 2. Punycode IDN homograph attack
        if "xn--" in host:
            return {
                "url": url,
                "is_suspicious": True,
                "severity": 0.90,
                "reason": "Punycode (IDN) domain detected, potential homograph spoofing",
            }

        # 3. Typo-squatting / Brand spoofing (e.g. micros0ft, goog1e, pay-pal)
        norm_host = (
            host.replace("0", "o")
            .replace("1", "l")
            .replace("3", "e")
            .replace("5", "s")
            .replace("@", "a")
        )
        norm_host_alt = host.replace("1", "i")

        for brand in self.BRAND_TARGETS:
            if (brand in norm_host or brand in norm_host_alt) and brand not in host:
                return {
                    "url": url,
                    "is_suspicious": True,
                    "severity": 0.95,
                    "reason": f"Typo-squatting impersonation of '{brand}' (leetspeak detected in '{host}')",
                }

            # Check for subdomain trickery e.g. microsoft.com.attacker.com or login-microsoft
            if brand in host and not (host.endswith(f".{brand}.com") or host == f"{brand}.com"):
                # Potential brand name embedding in rogue domain
                return {
                    "url": url,
                    "is_suspicious": True,
                    "severity": 0.85,
                    "reason": f"Brand name '{brand}' embedded in unverified domain '{host}'",
                }

        # 4. Credential harvester path patterns
        harvester_paths = ["/login", "/signin", "/verify", "/reset", "/update-billing", "/auth"]
        if any(hp in path for hp in harvester_paths) and any(kw in host for kw in ["account", "security", "portal", "verify"]):
            return {
                "url": url,
                "is_suspicious": True,
                "severity": 0.75,
                "reason": "Likely credential harvesting landing page structure",
            }

        # 5. Shannon entropy check for randomized DGA domains
        entropy = self._shannon_entropy(host)
        if entropy > 4.2 and len(host) > 15:
            return {
                "url": url,
                "is_suspicious": True,
                "severity": 0.70,
                "reason": f"High domain name entropy ({entropy:.2f}), probable DGA / disposable host",
            }

        return {
            "url": url,
            "is_suspicious": False,
            "severity": 0.0,
            "reason": "No suspicious URL indicators found",
        }

    @staticmethod
    def _shannon_entropy(string: str) -> float:
        if not string:
            return 0.0
        prob = [float(string.count(c)) / len(string) for c in set(string)]
        return -sum(p * math.log2(p) for p in prob)

    def _generate_recommendations(
        self,
        indicators: list[ThreatIndicator],
        vectors: set[str],
        urls: list[dict[str, Any]],
    ) -> list[str]:
        recs = []
        if "SET_SPEAR_PHISHING" in vectors:
            recs.append("DO NOT comply with urgency demands. Verify sender out-of-band via trusted internal directory.")
        if "SET_CREDENTIAL_HARVESTER" in vectors:
            recs.append("DO NOT enter credentials or MFA tokens on any linked portal. Check domain certificate and domain registrar.")
        if "SET_INFECTIOUS_MEDIA" in vectors:
            recs.append("DO NOT download, unpack, or execute attachments. Quarantine file immediately for sandbox detonation.")
        if "SET_POWERSHELL_PAYLOAD" in vectors:
            recs.append("BLOCK PowerShell execution immediately. Isolate host network interface and trigger SIEM alert.")

        if not recs:
            recs.append("No active social engineering threats detected. Exercise standard security hygiene.")

        return recs


_DETECTOR: SocialEngineeringDetector | None = None


def get_social_engineering_detector() -> SocialEngineeringDetector:
    """Singleton getter for SocialEngineeringDetector."""
    global _DETECTOR
    if _DETECTOR is None:
        _DETECTOR = SocialEngineeringDetector()
    return _DETECTOR
