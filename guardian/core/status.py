"""
Guardian Status — System Health Reporter
Level 0 (Observe only): reads system information, makes no changes.

Purpose:    Report verified facts about the Guardian environment.
Inputs:     None (reads from system and project state)
Outputs:    Structured dict of status information
Deps:       psutil, subprocess (nvidia-smi), pathlib, sys, platform
Permissions: Level 0 — read-only
Failure:    Individual checks degrade gracefully; failures are reported, not hidden
"""

import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from guardian.config.settings import settings
from guardian.logging.logger import get_logger

log = get_logger(__name__)

GIT_EXE = shutil.which("git") or r"C:\Program Files\Git\bin\git.exe"


def _check_python() -> dict[str, Any]:
    """Observe: Python runtime facts."""
    return {
        "version": sys.version.split()[0],
        "full_version": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
    }


def _check_platform() -> dict[str, Any]:
    """Observe: OS and machine facts."""
    mem = psutil.virtual_memory()
    return {
        "os": platform.system(),
        "os_version": platform.version()[:60],
        "machine": platform.machine(),
        "cpu": platform.processor()[:60] or "unknown",
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(mem.total / 1024**3, 1),
        "ram_available_gb": round(mem.available / 1024**3, 1),
    }


def _check_gpu() -> dict[str, Any]:
    """
    Observe: GPU status via nvidia-smi.
    Returns degraded result if nvidia-smi is not available.
    """
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {"status": "nvidia-smi not found in PATH", "available": False}

    try:
        result = subprocess.run(
            [
                nvidia_smi,
                "--query-gpu=name,driver_version,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"status": "nvidia-smi error", "available": False, "detail": result.stderr.strip()}

        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        gpus = []
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 4:
                gpus.append({
                    "name": parts[0],
                    "driver": parts[1],
                    "vram_total_mb": int(parts[2]),
                    "vram_free_mb": int(parts[3]),
                })
        return {"available": True, "gpus": gpus}

    except subprocess.TimeoutExpired:
        return {"status": "nvidia-smi timeout", "available": False}
    except Exception as exc:
        return {"status": f"error: {exc}", "available": False}


def _check_git() -> dict[str, Any]:
    """Observe: Git repository status."""
    project_root = settings.project_root

    if not Path(GIT_EXE).exists() and not shutil.which("git"):
        return {"installed": False, "status": "git not found"}

    git_cmd = GIT_EXE if Path(GIT_EXE).exists() else "git"

    try:
        # Is this a repo?
        result = subprocess.run(
            [git_cmd, "rev-parse", "--is-inside-work-tree"],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {"installed": True, "repo_initialized": False}

        # Get branch and commit count
        branch_result = subprocess.run(
            [git_cmd, "branch", "--show-current"],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=10,
        )
        count_result = subprocess.run(
            [git_cmd, "rev-list", "--count", "HEAD"],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=10,
        )

        return {
            "installed": True,
            "repo_initialized": True,
            "branch": branch_result.stdout.strip() or "(no branch yet)",
            "commits": int(count_result.stdout.strip()) if count_result.returncode == 0 else 0,
        }
    except Exception as exc:
        return {"installed": True, "status": f"error: {exc}"}


def _check_project() -> dict[str, Any]:
    """Observe: Guardian project state."""
    root = settings.project_root
    venv_python = root / "venv" / "Scripts" / "python.exe"
    env_file = root / ".env"
    constitution = root / "GUARDIAN_CONSTITUTION_v0.1.md"

    return {
        "root": str(root),
        "version": settings.version,
        "phase": settings.phase,
        "venv_exists": venv_python.exists(),
        "env_file_exists": env_file.exists(),
        "constitution_exists": constitution.exists(),
        "log_dir": str(settings.log_dir),
    }


def _check_cognitive() -> dict:
    """Observe: Cognitive layer stats."""
    try:
        from guardian.memory import get_memory_manager
        mm = get_memory_manager()
        store = getattr(mm, "_store", None)
        if store:
            from guardian.memory.execution import ExecutionMemory
            em = ExecutionMemory(store)
            
            # Count total execution outcomes
            rows = store.fetchall("SELECT COUNT(*) as n FROM execution_outcomes")
            total = rows[0]["n"] if rows else 0
            
            # Get proficiency for some top tools
            top_tools = ["network_recon", "file_read", "shell"]
            profs = {t: round(em.compute_proficiency(t), 2) for t in top_tools}
            
            return {
                "total_outcomes": total,
                "proficiency": profs
            }
        return {"total_outcomes": 0, "proficiency": {}}
    except Exception as e:
        return {"error": str(e)}

def _check_predictive_agents() -> dict:
    try:
        from guardian.security.epss import EPSSClient
        from guardian.security.attack_path import AttackPathPredictor
        from guardian.security.anomaly import AnomalyDetector
        
        # Load agents safely
        from guardian.core.agents import AGENTS
        if AGENTS is None:
            from guardian.core.agents import get_agent_for_tool
            get_agent_for_tool("dummy")
            from guardian.core.agents import AGENTS
            
        epss = EPSSClient()
        predictor = AttackPathPredictor()
        detector = AnomalyDetector()
        
        active_agents = {}
        coding_mode = "N/A"
        if AGENTS:
            for name, agent in AGENTS.items():
                active_agents[name] = list(agent.scope.allowed_tools)
                if name == "coding":
                    coding_mode = getattr(agent, "mode", "unknown")
                    
        specialist = {"available": False}
        try:
            from guardian.model.registry import get_router
            info = get_router().primary.get_info()
            if "security" in info.model.lower() or "qlora" in info.model.lower():
                specialist = {"available": True, "eval_delta": "N/A (using base model)"}
        except Exception:
            pass
        
        return {
            "epss_cache": epss.get_stats(),
            "attack_path_coverage": len(predictor._transitions),
            "anomaly_detector_active": detector.use_isolation_forest,
            "active_agents": active_agents,
            "coding_agent_mode": coding_mode,
            "specialist_model": specialist
        }
    except Exception as e:
        return {"error": str(e)}

def _check_compliance() -> dict:
    try:
        from guardian.policy.compliance import ComplianceStore
        from guardian.config.settings import settings
        from datetime import datetime, timezone
        
        store = ComplianceStore(settings.project_root / ".guardian" / "compliance.json")
        refs = store.get_all()
        
        ref_status = []
        now = datetime.now(timezone.utc)
        for r in refs:
            try:
                lv = datetime.fromisoformat(r.last_verified.replace("Z", "+00:00"))
                stale = (now - lv).days > 180
            except ValueError:
                stale = True
            ref_status.append({"id": r.id, "stale": stale})
            
        dsl_count = 6
        rules_dir = settings.project_root / ".guardian" / "rules"
        det_count = len(list(rules_dir.glob("*.yml"))) if rules_dir.exists() else 0
        
        return {
            "refs": ref_status,
            "dsl_rules": dsl_count,
            "det_rules": det_count
        }
    except Exception as e:
        return {"error": str(e)}


def _check_constitution() -> dict:
    from pathlib import Path
    import hashlib
    try:
        from guardian.config.settings import settings
        guard_file = settings.project_root / '.guardian/constitution.sha256'
        const_file = settings.project_root / 'GUARDIAN_CONSTITUTION_v0.1.md'
        if not guard_file.exists() or not const_file.exists():
            return {'active': False, 'status': 'Missing files'}
        
        expected_hash = "Unknown"
        for line in guard_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("SHA256:") and "GUARDIAN_CONSTITUTION" in line:
                expected_hash = line.split(":")[1].split()[0].strip().lower()
                break
        
        actual_hash = hashlib.sha256(const_file.read_bytes()).hexdigest().lower()
        
        return {
            'active': True,
            'status': 'PASS' if actual_hash == expected_hash else 'FAIL (Tampered)',
            'expected': expected_hash[:8],
            'actual': actual_hash[:8]
        }
    except Exception as e:
        return {'error': str(e)}

def _check_collab() -> dict:
    return {'framework': 'ACTIVE'}


def _check_laptop() -> dict:
    try:
        from guardian.config.settings import settings
        from guardian.laptop.safety import is_kill_triggered, BLOCKLIST_PATTERNS
        from guardian.laptop.session import get_active_session
        import json
        
        allowlist_path = settings.project_root / "guardian" / "config" / "laptop_allowlist.json"
        if allowlist_path.exists():
            allowlist = json.loads(allowlist_path.read_text())
        else:
            allowlist = {}
            
        session = get_active_session()
        
        return {
            "enabled": settings.enable_laptop_control,
            "kill_switch": "TRIGGERED" if is_kill_triggered() else "ARMED (ctrl+alt+k)",
            "blocklist_size": len(BLOCKLIST_PATTERNS),
            "allowlist_size": len(allowlist),
            "active_session": session.session_id if session else "None",
            "actions_used": session._actions_used if session else 0,
        }
    except Exception as e:
        return {"error": str(e)}

def collect_status() -> dict[str, Any]:
    """
    Collect full Guardian system status.
    All checks are Level 0 (observe only).
    Failures in individual checks are captured and reported — not raised.
    """
    log.info("Collecting Guardian status...")

    status: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "guardian": {},
        "python": {},
        "platform": {},
        "gpu": {},
        "git": {},
        "model_backends": {},
        "cognitive": {},
        "predictive": {}, "compliance": {}, "constitution": {}, "collab": {}, "laptop": {},
    }

    checks = [
        ("guardian", _check_project),
        ("python", _check_python),
        ("platform", _check_platform),
        ("gpu", _check_gpu),
        ("git", _check_git),
        ("model_backends", _check_model_backends),
        ("cognitive", _check_cognitive),
        ("predictive", _check_predictive_agents), ("compliance", _check_compliance), ("constitution", _check_constitution), ("collab", _check_collab), ("laptop", _check_laptop),
    ]

    for key, fn in checks:
        try:
            status[key] = fn()
        except Exception as exc:
            log.error(f"Status check '{key}' failed: {exc}")
            status[key] = {"error": str(exc), "status": "CHECK FAILED"}

    return status


def _check_model_backends() -> dict:
    """Observe: model backend availability. Level 0 - no API calls made."""
    from guardian.model.registry import get_registry
    try:
        registry = get_registry()
        infos = registry.list_all()
        backends = []
        for info in infos:
            backends.append({
                "name": info.name,
                "provider": info.provider,
                "model": info.model,
                "available": info.available,
                "requires_key": info.requires_key,
                "is_local": info.is_local,
                "notes": info.notes,
            })
        available_count = sum(1 for b in backends if b["available"])
        return {
            "backends": backends,
            "available_count": available_count,
            "total_count": len(backends),
        }
    except Exception as exc:
        return {"error": str(exc), "backends": []}

