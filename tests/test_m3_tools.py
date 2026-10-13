import pytest
from unittest.mock import patch
from guardian.tools.code_exec import CodeExecTool
from guardian.tools.db_query import DbQueryTool
from guardian.tools.network_recon import NetworkReconTool
from guardian.tools.git_tool import GitWriteTool, GitReadTool
from guardian.tools.base import ToolLevel
from guardian.policy import get_policy_engine

def test_code_exec_timeout(tmp_path):
    tool = CodeExecTool(enable_feature=True, timeout=1)
    # A runaway process
    code = "import time\nwhile True: time.sleep(0.1)"
    result = tool._execute({"code": code, "_sandbox": tmp_path})
    assert not result.success
    assert "timed out" in result.error

def test_code_exec_floor():
    tool = CodeExecTool()
    assert tool.level >= ToolLevel.DANGEROUS

def test_network_recon_floor():
    tool = NetworkReconTool()
    assert tool.level >= ToolLevel.DANGEROUS
    assert tool.requires_scope is True

def test_db_query_rejects_non_select(tmp_path):
    tool = DbQueryTool()
    
    # 1. Reject UPDATE
    res = tool._execute({"query": "UPDATE logs SET x=1", "_sandbox": tmp_path})
    assert not res.success
    assert "Only SELECT" in res.error
    
    # 2. Reject DELETE
    res = tool._execute({"query": "DELETE FROM logs", "_sandbox": tmp_path})
    assert not res.success
    assert "Only SELECT" in res.error
    
def test_network_recon_denies_out_of_scope(tmp_path):
    # This tests that the policy engine blocks an out-of-scope target
    # We will simulate a call to PolicyEngine with a network_recon tool call
    engine = get_policy_engine()
    
    # Assuming there's no scope file loaded, requires_scope=True will fail it
    decision = engine.evaluate(
        tool_name="network_recon",
        tool_level=2,
        params={"target": "10.0.0.1"},
        registered_tools={"network_recon"},
        target_arg="target",
        requires_scope=True
    )
    
    assert decision.effect.value == "deny"
    assert "no valid scope file loaded" in decision.reason
