import pytest
import time
from unittest.mock import patch, MagicMock
from guardian.tools.executor import ToolExecutor, TokenBucket, TTLCache
from guardian.tools.base import ToolRequest, ToolResult, Tool, ToolLevel
from guardian.core.orchestrator import GuardianCore, Session
from guardian.model.backends.mock import MockBackend
from guardian.model.interface import ModelResponse, TokenUsage

class DummyCachedTool(Tool):
    name = "dummy_cache"
    level = ToolLevel.READ
    description = ""
    cache_ttl = 1.0
    execute_count = 0
    def _execute(self, params):
        self.execute_count += 1
        return ToolResult(success=True, output=f"run {self.execute_count}")

class DummyNoCacheTool(Tool):
    name = "dummy_no_cache"
    level = ToolLevel.READ
    description = ""
    execute_count = 0
    def _execute(self, params):
        self.execute_count += 1
        return ToolResult(success=True, output=f"run {self.execute_count}")

def test_rate_limit_trips_and_recovers(tmp_path):
    executor = ToolExecutor(sandbox_root=tmp_path)
    tool = DummyNoCacheTool()
    executor.register(tool)
    
    # Force a small capacity and slow fill rate so it doesn't fill before execution
    bucket = TokenBucket(capacity=1, fill_rate=10.0) 
    bucket.tokens = 0
    bucket.last_fill = time.monotonic()
    
    executor._rate_limiters[("dummy_no_cache", "test_session")] = bucket
    
    # Because tokens = 0 and fill_rate is 10/s, it won't fill 1 token instantly
    req = ToolRequest(name="dummy_no_cache", params={}, session_id="test_session")
    res = executor.run(req)
    assert not res.success
    assert "Rate limit exceeded" in res.error
    
    # Wait for recovery (fill_rate is 10/sec, so 0.15s gives 1.5 tokens)
    time.sleep(0.15)
    res2 = executor.run(req)
    assert res2.success

def test_cost_estimate_recorded():
    mock = MockBackend()
    mock.name = "gemini-2.5-flash"
    core = GuardianCore(model=mock)
    session = Session()
    
    with patch("guardian.model.backends.mock.MockBackend.complete") as mock_complete:
        mock_complete.return_value = ModelResponse(
            content="Hello", 
            provider="mock", 
            model="gemini-2.5-flash",
            usage=TokenUsage(prompt_tokens=1_000_000, completion_tokens=2_000_000, total_tokens=3_000_000)
        )
        
        with patch("guardian.audit.get_audit_log") as mock_audit:
            core.process("test", session)
            
            # The exact math for gemini-2.5-flash is 0.075 + 2 * 0.30 = 0.675
            mock_audit.return_value.append.assert_any_call(
                "model.usage",
                session_id="",
                payload={
                    "model": "gemini-2.5-flash",
                    "prompt_tokens": 1000000,
                    "completion_tokens": 2000000,
                    "total_tokens": 3000000,
                    "estimated_cost_usd": 0.675
                }
            )

def test_cache_hit_and_bypass(tmp_path):
    executor = ToolExecutor(sandbox_root=tmp_path)
    cached_tool = DummyCachedTool()
    no_cache_tool = DummyNoCacheTool()
    executor.register(cached_tool)
    executor.register(no_cache_tool)
    
    req_cache = ToolRequest(name="dummy_cache", params={"q": "1"})
    req_no = ToolRequest(name="dummy_no_cache", params={"q": "1"})
    
    # Run once
    executor.run(req_cache)
    executor.run(req_no)
    assert cached_tool.execute_count == 1
    assert no_cache_tool.execute_count == 1
    
    # Run twice
    executor.run(req_cache)
    executor.run(req_no)
    
    # Cache hit for cached_tool, execute_count stays 1
    assert cached_tool.execute_count == 1
    # Cache bypass for no_cache_tool, execute_count is 2
    assert no_cache_tool.execute_count == 2
