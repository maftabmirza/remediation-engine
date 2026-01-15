import asyncio
import sys
import os
import logging
from unittest.mock import MagicMock, patch, AsyncMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add app to path
sys.path.append(os.getcwd())

from app.services.agentic.orchestrator import AgenticOrchestrator
from app.models import LLMProvider, Alert
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup DB connection (assuming local docker environment variables or defaults)
# We'll use a mock DB session if we can't connect, but let's try to be "real" if possible
# or just Mock the DB session but let the tool registry logic run.
# Given we are in the container, we have access to the real DB via existing code pattern if usage allows.
# For this targeted test, we'll Mock the DB to avoid connectivity issues but ensure the AGENT logic flows.

async def run_simulation():
    print("\n--- Starting End-to-End Use Case Simulation ---\n")
    
    # 1. Setup Mock Provider (OpenAI-like)
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.provider_type = "openai"
    mock_provider.model_id = "gpt-4"
    mock_provider.config_json = {"temperature": 0.3}
    mock_provider.api_key_encrypted = "test-key"
    mock_provider.api_base_url = None

    # 2. Setup Mock Alert
    mock_alert = MagicMock(spec=Alert)
    mock_alert.id = "12345678-1234-5678-1234-567812345678"
    mock_alert.alert_name = "High CPU Usage"
    mock_alert.severity = "critical"
    mock_alert.instance = "api-server-01"
    mock_alert.status = "firing"
    mock_alert.annotations_json = {"summary": "CPU utilization > 90%"}

    # 3. Setup Mock DB (We want to verify TOOL LOGIC, not DB connectivity)
    mock_db = MagicMock()
    
    # Initialize Orchestrator
    orchestrator = AgenticOrchestrator(mock_db, mock_provider, mock_alert)
    print(f"✅ Orchestrator initialized with {orchestrator.agent_type}")
    
    # 4. Mock the LLM Response to trigger a tool call
    # We patch the `_call_llm` method of the underlying agent
    
    # Sequence of LLM responses:
    # 1. Request to call 'search_knowledge'
    # 2. Final answer based on observation
    
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_abc123"
    mock_tool_call.function.name = "search_knowledge"
    mock_tool_call.function.arguments = '{"query": "CPU high troubleshooting"}'
    mock_tool_call.type = "function"
    
    response_1_message = MagicMock()
    response_1_message.content = None
    response_1_message.tool_calls = [mock_tool_call]
    
    response_1 = MagicMock()
    response_1.choices = [MagicMock(message=response_1_message)]
    
    response_2_message = MagicMock()
    response_2_message.content = "Based on the runbook, you should check for runaway processes."
    response_2_message.tool_calls = None
    
    response_2 = MagicMock()
    response_2.choices = [MagicMock(message=response_2_message)]

    # We also need to Mock the ToolRegistry execution to return something readable
    # because we mocked the DB, so the real tool would fail on DB queries.
    # verify_agent_tools.py verified REGISTRY initialization.
    # This script verifies the AGENT'S usage of the registry.
    
    print("\n[Simulation] User: 'Why is the CPU high on api-server-01?'")
    
    with patch.object(orchestrator._agent, '_call_llm', side_effect=[response_1, response_2]):
        with patch.object(orchestrator._agent.tool_registry, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = "Found Runbook: Check Docker containers for high CPU."
            
            response = await orchestrator.run("Why is the CPU high on api-server-01?")
            
            # Verification Steps
            print(f"\n[Agent] Iterations: {response.iterations}")
            print(f"[Agent] Final Content: {response.content}")
            print(f"[Agent] Tool Calls Made: {response.tool_calls_made}")
            
            if "search_knowledge" in response.tool_calls_made:
                print("✅ TEST PASSED: Agent successfully decided to call 'search_knowledge'")
            else:
                print("❌ TEST FAILED: Agent did not call expected tool")
                
            if mock_execute.called:
                 args, _ = mock_execute.call_args
                 print(f"✅ TEST PASSED: ToolRegistry.execute was called with: {args}")
            else:
                 print("❌ TEST FAILED: ToolRegistry was not executed")

if __name__ == "__main__":
    asyncio.run(run_simulation())
