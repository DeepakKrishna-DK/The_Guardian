import pytest
from guardian.policy.engine import _check_scope, _load_scope
from guardian.policy.compliance import ComplianceStore, ComplianceReference
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

def test_scope_authorization_basis(tmp_path):
    scope_file = tmp_path / "scope.json"
    
    # 1. Missing authorization_basis -> reject
    scope_file.write_text(json.dumps({
        "targets": ["127.0.0.1"]
    }))
    ok, reason, auth = _check_scope("127.0.0.1", str(scope_file), None, False)
    assert not ok
    assert "missing required authorization_basis" in reason
    
    # 2. Expired authorization_basis -> reject
    expired_date = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
    scope_file.write_text(json.dumps({
        "targets": ["127.0.0.1"],
        "authorization_basis": {
            "basis_type": "written permission",
            "date": expired_date
        }
    }))
    ok, reason, auth = _check_scope("127.0.0.1", str(scope_file), None, False)
    assert not ok
    assert "expired" in reason
    
    # 3. Valid authorization_basis -> allow
    valid_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    scope_file.write_text(json.dumps({
        "targets": ["127.0.0.1"],
        "authorization_basis": {
            "basis_type": "written permission",
            "date": valid_date
        }
    }))
    ok, reason, auth = _check_scope("127.0.0.1", str(scope_file), None, False)
    assert ok
    assert auth["basis_type"] == "written permission"
    
def test_compliance_reference_crud(tmp_path):
    store = ComplianceStore(tmp_path / "comp.json")
    
    ref = ComplianceReference(
        id="test1",
        title="Test Law",
        description="A test description.",
        source_url="http://example.com",
        last_verified="2026-10-03T12:00:00Z"
    )
    store.add_or_update(ref)
    
    loaded = store.get("test1")
    assert loaded is not None
    assert loaded.title == "Test Law"
    
    store.delete("test1")
    assert store.get("test1") is None
