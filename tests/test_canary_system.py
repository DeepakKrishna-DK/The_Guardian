"""
Tests for Autonomous Canary & Honeypot Token System
===================================================
"""

from pathlib import Path
import pytest
from guardian.security.canary import CanaryManager, CanaryType
from guardian.security.gateway import SecurityGateway, SecurityContext


@pytest.fixture
def temp_canary_mgr(tmp_path: Path):
    storage = tmp_path / "canary_reg.json"
    mgr = CanaryManager(storage_path=storage, workspace_root=tmp_path)
    return mgr


def test_plant_decoy_secret(temp_canary_mgr: CanaryManager):
    token = temp_canary_mgr.plant_decoy_secret("aws_prod_key", secret_prefix="AKIA_CANARY_")
    assert token.id
    assert token.name == "aws_prod_key"
    assert token.token_type == CanaryType.DECOY_SECRET.value
    assert token.value.startswith("AKIA_CANARY_")
    assert not token.triggered

    # Verify persistent reload
    reloaded = temp_canary_mgr.get_token(token.id)
    assert reloaded is not None
    assert reloaded.value == token.value


def test_plant_honey_file(temp_canary_mgr: CanaryManager):
    token = temp_canary_mgr.plant_honey_file("db_creds", relative_path="sub/db.env")
    assert token.file_path
    p = Path(token.file_path)
    assert p.exists()
    assert token.expected_hash
    assert not token.triggered

    # Integrity check on pristine file must pass
    alerts = temp_canary_mgr.check_integrity()
    assert len(alerts) == 0


def test_honey_file_tamper_detected(temp_canary_mgr: CanaryManager):
    token = temp_canary_mgr.plant_honey_file("tamper_test")
    p = Path(token.file_path)
    assert p.exists()

    # Tamper with file
    p.write_text("TAMPERED DATA INJECTED BY ATTACKER", encoding="utf-8")

    alerts = temp_canary_mgr.check_integrity()
    assert len(alerts) == 1
    assert alerts[0]["status"] == "TAMPERED_MODIFIED"
    assert alerts[0]["token_id"] == token.id

    # Verify marked triggered
    updated_token = temp_canary_mgr.get_token(token.id)
    assert updated_token.triggered
    assert updated_token.trigger_count >= 1


def test_honey_file_deletion_detected(temp_canary_mgr: CanaryManager):
    token = temp_canary_mgr.plant_honey_file("delete_test")
    p = Path(token.file_path)
    p.unlink()

    alerts = temp_canary_mgr.check_integrity()
    assert len(alerts) == 1
    assert alerts[0]["status"] == "TAMPERED_DELETED"


def test_inspect_text_leak(temp_canary_mgr: CanaryManager):
    token = temp_canary_mgr.plant_decoy_secret("api_token")
    assert not token.triggered

    # Non-matching text
    tripped = temp_canary_mgr.inspect_text_leak("Normal non-sensitive text")
    assert len(tripped) == 0

    # Text containing the canary secret
    tripped = temp_canary_mgr.inspect_text_leak(f"Exfiltrating data: {token.value}")
    assert len(tripped) == 1
    assert tripped[0].id == token.id
    assert tripped[0].triggered


def test_gateway_intercepts_canary_output(temp_canary_mgr: CanaryManager):
    token = temp_canary_mgr.plant_decoy_secret("secret_token")
    gw = SecurityGateway()
    gw.canary = temp_canary_mgr

    ctx = SecurityContext(
        request_id="req1",
        user_id="user1",
        tenant_id="",
        authentication_status=True,
        risk_level="low",
        data_classification="public",
        security_flags=[],
        allowed_tools=set(),
        rate_limit_status="ok",
        policy_decision="allow",
    )

    # Safe output allowed
    safe_res = gw.check_output("Here is the requested public documentation.", ctx)
    assert safe_res.allowed

    # Output leaking canary secret must be intercepted
    leak_output = f"Here is the database password: {token.value}"
    leak_res = gw.check_output(leak_output, ctx)
    assert not leak_res.allowed
    assert "Canary secret exfiltration" in leak_res.reason
