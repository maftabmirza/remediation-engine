import asyncio
import sys
import os
import logging
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)

# Add app to path
sys.path.append(os.getcwd())

from app.services.agentic.native_agent import NativeToolAgent
from app.models import LLMProvider
from litellm.exceptions import APIConnectionError

async def reproduce_error():
    print("--- Reproducing APIConnectionError ---")
    
    # Mock Provider
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.provider_type = "anthropic"
    mock_provider.model_id = "claude-3-opus"
    mock_provider.api_key_encrypted = "test-key"
    
    agent = NativeToolAgent(MagicMock(), mock_provider)
    
    # Simulate APIConnectionError from LiteLLM
    # The error message suggests that 'APIConnectionError' object has no attribute 'response'
    # This likely happens when accessing e.response inside an exception handler or logging
    
    with patch('app.services.agentic.native_agent.acompletion') as mock_acompletion:
        # Create an exception that mimics the structure causing the issue
        # LiteLLM's APIConnectionError typically wraps an underlying request error
        
        # We need to simulate the exact conditions under which the error occurs.
        # However, the log says: Agent stream error: 'APIConnectionError' object has no attribute 'response'
        # This implies that somewhere in the code (or LiteLLM internals), 'response' is being accessed on the exception object.
        
        # Looking at native_agent.py, the exception handler just logs str(e):
        # logger.error(f"Agent stream error: {e}")
        
        # This implies the error might be happening INSIDE str(e) or repr(e) of the exception?
        # OR, it's happening inside LiteLLM's acompletion before it returns.
        
        mock_acompletion.side_effect = APIConnectionError(
            message="Connection failed",
            llm_provider="anthropic",
            model="claude-3-opus",
            request=MagicMock()
        )
        
        try:
            print("Running agent...")
            async for chunk in agent.stream("test"):
                print(chunk)
        except Exception as e:
            print(f"Caught top-level exception: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(reproduce_error())
