import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add app to path
sys.path.append(os.getcwd())

from app.services.agentic.orchestrator import AgenticOrchestrator
from app.services.agentic.native_agent import AgentResponse

async def verify():
    print("--- Verifying AgenticOrchestrator Setup ---")
    
    # Mock dependencies
    mock_db = MagicMock()
    mock_provider = MagicMock()
    mock_provider.provider_type = "openai"
    mock_provider.model_id = "gpt-4"
    mock_provider.config_json = {"temperature": 0.3}
    mock_provider.api_key_encrypted = "test"
    
    # Initialize implementation
    try:
        orchestrator = AgenticOrchestrator(mock_db, mock_provider)
        print("✅ AgenticOrchestrator initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize orchestrator: {e}")
        return

    # Verify Agent Type
    if orchestrator.agent_type == "NativeToolAgent":
        print(f"✅ Correctly selected NativeToolAgent for provider 'openai'")
    else:
        print(f"❌ Incorrect agent type: {orchestrator.agent_type}")
        
    # Verify Tools
    tools = orchestrator._agent.tool_registry.get_tools()
    tool_names = [t.name for t in tools]
    expected_tools = [
        "search_knowledge", "get_similar_incidents", "get_recent_changes",
        "get_runbook", "query_grafana_metrics", "query_grafana_logs",
        "get_correlated_alerts", "get_service_dependencies", 
        "get_feedback_history", "get_alert_details"
    ]
    
    missing = [t for t in expected_tools if t not in tool_names]
    
    if not missing:
        print(f"✅ All {len(expected_tools)} expected tools are registered")
    else:
        print(f"❌ Missing tools: {missing}")

    # Verify Run Method
    orchestrator._agent.run = AsyncMock(return_value=AgentResponse(
        content="Success", 
        tool_calls_made=["search_knowledge"], 
        iterations=1, 
        finished=True
    ))
    
    response = await orchestrator.run("Test message")
    
    if response.content == "Success":
        print("✅ orchestrator.run() execution verified")
    else:
        print("❌ orchestrator.run() failed")

if __name__ == "__main__":
    asyncio.run(verify())
