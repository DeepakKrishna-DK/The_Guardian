"""
Guardian Configuration System
Loads settings from environment variables and .env file.
All secrets come from environment — never hardcoded.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is two levels up from this file
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class GuardianSettings(BaseSettings):
    """
    Central configuration for AI Guardian.
    Values are loaded from environment variables or .env file.
    Defaults are safe and non-destructive.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="GUARDIAN_",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Project Identity ---
    project_name: str = Field(default="AI Guardian", description="Project name")
    version: str = Field(default="0.1.0", description="Guardian version")
    phase: str = Field(default="Phase 1 — Project Foundation", description="Current development phase")

    # --- Paths ---
    project_root: Path = Field(default=PROJECT_ROOT, description="Absolute project root path")
    log_dir: Path = Field(default=PROJECT_ROOT / "logs", description="Log output directory")
    data_dir: Path = Field(default=PROJECT_ROOT / "data", description="Runtime data directory")

    # --- Logging ---
    log_level: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR")
    log_format: str = Field(default="json", description="Log format: json or text")

    # --- Security ---
    workspace_boundary: Path = Field(
        default=PROJECT_ROOT,
        description="Guardian may not write files outside this path without approval"
    )
    enable_laptop_control: bool = Field(
        default=False, 
        description="FEATURE FLAG: Enable laptop control capabilities. OFF by default."
    )

    def ensure_directories(self) -> None:
        """Create required runtime directories if they do not exist."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)


# Module-level singleton — import this throughout Guardian
settings = GuardianSettings()
