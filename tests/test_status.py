"""
Tests for guardian.core.status
Phase 1 — Project Foundation

These tests verify actual behaviour of the status checks.
They do NOT mock the system — they observe real values.
"""

import os
import sys
from pathlib import Path

import pytest

from guardian.config.settings import settings

# ─── Import under test ───────────────────────────────────────────────────────
from guardian.core.status import (
    _check_git,
    _check_gpu,
    _check_platform,
    _check_project,
    _check_python,
    collect_status,
)

# ─── Python check ────────────────────────────────────────────────────────────

class TestCheckPython:
    def test_returns_dict(self):
        result = _check_python()
        assert isinstance(result, dict)

    def test_version_matches_runtime(self):
        result = _check_python()
        # Must start with "3.13" on this machine
        assert result["version"].startswith("3.13"), (
            f"Expected Python 3.13.x, got {result['version']}"
        )

    def test_executable_exists(self):
        result = _check_python()
        assert Path(result["executable"]).exists(), (
            f"Executable not found: {result['executable']}"
        )

    def test_platform_field_present(self):
        result = _check_python()
        assert "platform" in result
        assert result["platform"] == sys.platform


# ─── Platform check ──────────────────────────────────────────────────────────

class TestCheckPlatform:
    def test_returns_dict(self):
        result = _check_platform()
        assert isinstance(result, dict)

    def test_os_is_valid(self):
        import platform
        result = _check_platform()
        assert result["os"] == platform.system()

    def test_ram_is_positive(self):
        result = _check_platform()
        assert result["ram_total_gb"] > 0
        assert result["ram_available_gb"] >= 0
        assert result["ram_total_gb"] >= result["ram_available_gb"]

    def test_cpu_cores_positive(self):
        result = _check_platform()
        assert result["cpu_cores_physical"] >= 1
        assert result["cpu_cores_logical"] >= result["cpu_cores_physical"]

    @pytest.mark.skipif("CI" in os.environ, reason="CI runners have different RAM capacity")
    def test_ram_approximately_16gb(self):
        """Machine is documented as 16 GB DDR5."""
        result = _check_platform()
        # Allow 14–18 GB to account for OS reservation
        assert 14 <= result["ram_total_gb"] <= 18, (
            f"Expected ~16 GB RAM, got {result['ram_total_gb']} GB"
        )


# ─── GPU check ───────────────────────────────────────────────────────────────

class TestCheckGpu:
    def test_returns_dict(self):
        result = _check_gpu()
        assert isinstance(result, dict)

    def test_has_available_key(self):
        result = _check_gpu()
        assert "available" in result

    def test_if_available_has_gpus(self):
        result = _check_gpu()
        if result.get("available"):
            assert "gpus" in result
            assert len(result["gpus"]) > 0
            gpu = result["gpus"][0]
            assert "name" in gpu
            assert "vram_total_mb" in gpu
            assert gpu["vram_total_mb"] > 0


# ─── Git check ───────────────────────────────────────────────────────────────

class TestCheckGit:
    def test_returns_dict(self):
        result = _check_git()
        assert isinstance(result, dict)

    def test_git_is_installed(self):
        result = _check_git()
        assert result.get("installed") is True, "Git must be installed (verified in Phase 0)"

    def test_repo_is_initialized(self):
        result = _check_git()
        assert result.get("repo_initialized") is True, (
            "Git repo must be initialized in Guardian workspace"
        )

    def test_branch_field_present_when_initialized(self):
        result = _check_git()
        if result.get("repo_initialized"):
            assert "branch" in result


# ─── Project check ───────────────────────────────────────────────────────────

class TestCheckProject:
    def test_returns_dict(self):
        result = _check_project()
        assert isinstance(result, dict)

    def test_constitution_exists(self):
        result = _check_project()
        assert result.get("constitution_exists") is True, (
            "GUARDIAN_CONSTITUTION_v0.1.md must exist in project root"
        )

    @pytest.mark.skipif("CI" in os.environ or not (Path(_check_project()["root"]) / "venv").exists(), reason="Skipped if running outside local venv or in CI")
    def test_venv_exists(self):
        result = _check_project()
        assert result.get("venv_exists") is True, (
            "Python venv must exist at Guardian/venv/"
        )

    def test_version_format(self):
        result = _check_project()
        assert result.get("version") == "0.1.0"

    def test_root_is_correct(self):
        result = _check_project()
        root = Path(result["root"])
        assert root.exists()
        assert (root / "GUARDIAN_CONSTITUTION_v0.1.md").exists()


# ─── Full status collection ───────────────────────────────────────────────────

class TestCollectStatus:
    def test_returns_dict(self):
        result = collect_status()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = collect_status()
        required = {"timestamp", "guardian", "python", "platform", "gpu", "git"}
        assert required.issubset(result.keys()), (
            f"Missing keys: {required - result.keys()}"
        )

    def test_no_section_is_empty(self):
        result = collect_status()
        for key in ["guardian", "python", "platform", "gpu", "git"]:
            assert result[key], f"Section '{key}' must not be empty"

    def test_timestamp_is_string(self):
        result = collect_status()
        assert isinstance(result["timestamp"], str)
        assert "T" in result["timestamp"]  # ISO format


# ─── Settings ────────────────────────────────────────────────────────────────

class TestSettings:
    def test_settings_loads(self):
        assert settings is not None

    def test_project_root_exists(self):
        assert settings.project_root.exists()

    def test_constitution_in_root(self):
        assert (settings.project_root / "GUARDIAN_CONSTITUTION_v0.1.md").exists()

    def test_version(self):
        assert settings.version == "0.1.0"
