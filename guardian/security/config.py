import os
from dataclasses import dataclass, field

@dataclass
class SecurityConfig:
    auth_required: bool = field(default_factory=lambda: os.environ.get("GUARDIAN_AUTH_REQUIRED", "false").lower() == "true")
    valid_tokens: list = field(default_factory=lambda: os.environ.get("GUARDIAN_VALID_TOKENS", "").split(",") if os.environ.get("GUARDIAN_VALID_TOKENS") else [])
    rate_limit_rpm: int = field(default_factory=lambda: int(os.environ.get("GUARDIAN_RATE_LIMIT_RPM", "60")))
    kill_switch_active: bool = field(default_factory=lambda: os.environ.get("GUARDIAN_KILL_SWITCH", "false").lower() == "true")

def get_security_config():
    return SecurityConfig()
