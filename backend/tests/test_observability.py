import logging
import os
from unittest.mock import patch

from agentic_traveler.core.observability import (
    hash_user_id,
    attach_run_metadata,
)

def test_hash_is_deterministic():
    with patch.dict(os.environ, {"LANGSMITH_HASH_KEY": "supersecretkey12345678901234567890"}):
        # Re-import or re-initialize of module flags is not needed if hmac reads it dynamically,
        # but let's mock _HASH_KEY inside hash_user_id by patching os.environ and refreshing _HASH_KEY:
        from agentic_traveler.core import observability
        with patch.object(observability, "_HASH_KEY", "supersecretkey12345678901234567890"):
            h1 = hash_user_id("user-uuid-12345")
            h2 = hash_user_id("user-uuid-12345")
            assert h1 == h2
            assert len(h1) == 64  # SHA256 hex digest is 64 chars

def test_hash_differs_across_users():
    from agentic_traveler.core import observability
    with patch.object(observability, "_HASH_KEY", "supersecretkey12345678901234567890"):
        h1 = hash_user_id("user-1")
        h2 = hash_user_id("user-2")
        assert h1 != h2

def test_hash_falls_back_when_no_key(caplog):
    from agentic_traveler.core import observability
    # Reset warned flag to ensure we trigger log
    observability._warned_no_hash_key = False
    
    with patch.object(observability, "_HASH_KEY", ""):
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            h1 = hash_user_id("some-user")
            assert h1 == "unknown"
            assert "LANGSMITH_HASH_KEY not set" in caplog.text
            
            # Second call should be silent
            caplog.clear()
            h2 = hash_user_id("other-user")
            assert h2 == "unknown"
            assert "LANGSMITH_HASH_KEY not set" not in caplog.text

def test_traceable_is_noop_when_disabled():
    import importlib
    from agentic_traveler.core import observability
    
    # Save current env
    orig_env = os.environ.get("LANGSMITH_TRACING")
    
    try:
        # Set tracing env to false and reload module to evaluate no-op decorator
        with patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}):
            importlib.reload(observability)
            
            with patch("langsmith.client.Client") as mock_client:
                @observability.traceable(name="test")
                def dummy_fn(x, y):
                    return x + y
                
                assert dummy_fn(2, 3) == 5
                mock_client.assert_not_called()
    finally:
        # Restore original env and reload module to restore previous state
        if orig_env is not None:
            os.environ["LANGSMITH_TRACING"] = orig_env
        elif "LANGSMITH_TRACING" in os.environ:
            del os.environ["LANGSMITH_TRACING"]
        importlib.reload(observability)


def test_attach_run_metadata_safe_when_disabled():
    from agentic_traveler.core import observability
    with patch.object(observability, "_TRACING_ENABLED", False):
        # Calling this when tracing is disabled should simply do nothing and not raise.
        attach_run_metadata(user_id_hash="xyz", custom_key="abc")

def test_no_pii_keys_in_metadata():
    from agentic_traveler.orchestrator.agent import OrchestratorAgent
    from agentic_traveler.tools.user_repo import UserRepository
    from unittest.mock import MagicMock

    mock_user_repo = MagicMock(spec=UserRepository)
    
    # We need to mock all external dependencies of OrchestratorAgent to run it
    with patch("agentic_traveler.orchestrator.agent.RouterAgent"), \
         patch("agentic_traveler.orchestrator.agent.SagaDispatcher"), \
         patch("agentic_traveler.orchestrator.agent.TripRepository"), \
         patch("agentic_traveler.orchestrator.agent.ConversationManager"), \
         patch("agentic_traveler.orchestrator.agent.credit_manager") as mock_credits, \
         patch("agentic_traveler.orchestrator.agent.off_topic_guard") as mock_guard, \
         patch("agentic_traveler.orchestrator.agent.get_client"), \
         patch("agentic_traveler.orchestrator.agent.attach_run_metadata") as mock_attach:
         
        mock_credits.has_credits.return_value = True
        mock_guard.is_restricted.return_value = None
        
        # Test 1: Telegram path (process_request)
        mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
        with patch.object(OrchestratorAgent, "_process_user_doc"):
            agent = OrchestratorAgent(user_repo=mock_user_repo)
            
            mock_attach.reset_mock()
            agent.process_request("telegram-user-123", "Hello")
            
            mock_attach.assert_called_once()
            kwargs = mock_attach.call_args.kwargs
            assert set(kwargs.keys()).issubset({"user_id_hash", "surface"})
            
            # Test 2: Web path (process_request_for_user)
            mock_attach.reset_mock()
            agent.process_request_for_user("user-id-123", "Hello")
            
            mock_attach.assert_called_once()
            kwargs = mock_attach.call_args.kwargs
            assert set(kwargs.keys()).issubset({"user_id_hash", "surface"})

