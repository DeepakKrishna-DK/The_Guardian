import pytest
from unittest.mock import patch
from guardian.core.orchestrator import GuardianCore, Session
from guardian.model.interface import ModelResponse, TokenUsage, ModelRequest
from guardian.model.backends.mock import MockBackend

def test_m6_self_critique():
    mock_backend = MockBackend()
    
    # We will patch the complete method to simulate a response and a critique
    call_count = 0
    def side_effect(request: ModelRequest) -> ModelResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ModelResponse(
                content="This is the main response, which is long enough to trigger critique.",
                provider="mock",
                model="guardian-mock-v1",
                usage=TokenUsage(10, 10, 20)
            )
        else:
            return ModelResponse(
                content="UNSAFE: Contains potentially harmful advice.",
                provider="mock",
                model="guardian-mock-v1",
                usage=TokenUsage(10, 10, 20)
            )

    core = GuardianCore(model=mock_backend, enable_self_critique=True)
    session = Session()

    with patch.object(mock_backend, 'complete', side_effect=side_effect):
        with patch("guardian.audit.get_audit_log") as mock_audit:
            response = core.process("Test prompt", session)
            
            # Verify the response is standard (critique is advisory and doesn't block)
            assert response.content == "This is the main response, which is long enough to trigger critique."
            
            # Verify that self_critique was audited as unsafe
            # First append is for model.usage, second is for self_critique, third is model.call
            mock_audit.return_value.append.assert_any_call(
                "model.self_critique",
                session_id="",
                payload={
                    "unsafe": True,
                    "critique_length": len("UNSAFE: Contains potentially harmful advice.")
                }
            )
