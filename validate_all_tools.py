import asyncio
import logging
import sys
from uuid import uuid4

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("validate_tools")

from app.database import SessionLocal
from app.services.agentic.tools.registry import create_full_registry

# Mock inputs for each tool
TOOL_INPUTS = {
    # Knowledge
    "search_knowledge": {"query": "apache restart", "doc_type": "runbook", "limit": 1},
    "get_similar_incidents": {"limit": 1}, # returns "No alert context" if no alert, which is safe/valid
    "get_runbook": {"service": "apache"},
    "get_proven_solutions": {"problem_description": "mysql slow query"},
    
    # Troubleshooting
    "get_recent_changes": {"service": "mysql", "hours_back": 24},
    "get_correlated_alerts": {}, # safe fallback
    "get_service_dependencies": {"service": "billing-service"},
    "get_feedback_history": {"limit": 1},
    "get_alert_details": {}, # safe fallback
    "suggest_ssh_command": {
        "server": "127.0.0.1", 
        "command": "echo 'test'", 
        "explanation": "validation test"
    },
    
    # Observability
    "query_grafana_metrics": {"promql": "up", "time_range": "1h"},
    "query_grafana_logs": {"logql": "{job=\"varlogs\"}", "limit": 1} 
}

async def validate_tools():
    print("🚀 Starting Tool Validation...")
    
    db = SessionLocal()
    try:
        # Initialize registry (no alert context)
        registry = create_full_registry(db, alert_id=None)
        
        tools = registry.get_tools()
        print(f"📦 Found {len(tools)} registered tools.")
        
        results = []
        
        for tool in tools:
            name = tool.name
            args = TOOL_INPUTS.get(name)
            
            if args is None:
                print(f"⚠️  Skipping {name}: No test args defined.")
                continue
                
            print(f"Testing {name}...", end=" ", flush=True)
            
            try:
                # Execute tool
                result = await registry.execute(name, args)
                
                # Check for "Error:" prefix strings which usually indicate handled failures
                # But we definitely want to catch Unhandled Exceptions (crashes)
                if result.startswith("Error executing"):
                    print("❌ CRASHED (Handled)")
                    print(f"   Output: {result}")
                    results.append((name, "CRASH"))
                else:
                    print("✅ OK")
                    results.append((name, "PASS"))
                    
            except Exception as e:
                print("💥 EXCEPTION (Unhandled)")
                print(f"   {type(e).__name__}: {e}")
                results.append((name, "EXCEPTION"))

        print("\n📊 Validation Summary:")
        crashes = [r for r in results if r[1] != "PASS"]
        if not crashes:
            print("🎉 ALL TOOLS PASSED! No runtime crashes detected.")
        else:
            print(f"🛑 Found {len(crashes)} issues:")
            for name, status in crashes:
                print(f"   - {name}: {status}")
                
    except Exception as e:
        print(f"Fatal Setup Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(validate_tools())
