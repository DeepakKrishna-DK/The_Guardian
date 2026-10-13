import pytest
from datetime import datetime, timedelta
from guardian.memory.store import MemoryStore
from guardian.memory.execution import ExecutionMemory

def test_execution_memory_proficiency():
    store = MemoryStore(":memory:")
    mem = ExecutionMemory(store)
    
    # Target starts neutral
    assert mem.compute_proficiency("nmap") == 0.5
    
    # Save a successful outcome
    mem.save_outcome("nmap", "tool", True, 120.0)
    assert mem.compute_proficiency("nmap") > 0.5
    
    # Save a failure
    mem.save_outcome("nmap", "tool", False, 10.0)
    prof_mixed = mem.compute_proficiency("nmap")
    assert 0.0 < prof_mixed < 1.0
    
    # Check that older items have less weight
    # We can fake it by directly inserting an old success
    old_ts = (datetime.now() - timedelta(days=30)).isoformat()
    store.execute(
        """
        INSERT INTO execution_outcomes 
          (id, target_id, target_type, success, duration_ms, risk_flags, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("old_1", "old_target", "tool", 1, 100.0, "[]", old_ts)
    )
    # Old success decays, so it won't be exactly 1.0 but rather the only item
    prof_old = mem.compute_proficiency("old_target")
    assert prof_old == 1.0 # only 1 item, so weight calculation yields 1.0 / 1.0 = 1.0
    
    # Wait, proficiency with only 1 item is always 1.0 or 0.0 if total_weight > 0.
    store.execute(
        """
        INSERT INTO execution_outcomes 
          (id, target_id, target_type, success, duration_ms, risk_flags, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("old_2", "old_target", "tool", 0, 100.0, "[]", datetime.now().isoformat())
    )
    # Now we have one very old success and one brand new failure.
    # The new failure should dominate the weight, dragging proficiency closer to 0.
    prof_decayed = mem.compute_proficiency("old_target")
    assert prof_decayed < 0.5
