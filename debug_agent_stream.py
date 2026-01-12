import asyncio
import json
from unittest.mock import MagicMock

async def mock_stream():
    # Simulate the variables in NativeToolAgent.stream
    
    # Mock Message from LLM
    message = MagicMock()
    message.content = "This is the reasoning text that should appear FIRST."
    
    # Mock Tool Call
    tc = MagicMock()
    tc.function.name = "suggest_ssh_command"
    tc.function.arguments = json.dumps({
        "server": "localhost", 
        "command": "echo hello",
        "explanation": "test"
    })
    tc.id = "call_123"
    
    tool_calls = [tc]
    
    # Simulate the loop logic from native_agent.py (AFTER my fix)
    
    # 1. Friendly Tool Notifications (Skip suggest_ssh_command)
    friendly_tool_names = {"suggest_ssh_command": "Suggesting..."}
    for tc in tool_calls:
        tool_name = tc.function.name
        if tool_name != "suggest_ssh_command":
            yield f"\n*Using {tool_name}*\n"
            
    # 2. Yield Content First (My Fix)
    if message.content:
        yield message.content
        
    # 3. Yield CMD_CARD
    command_suggested = False
    for tc in tool_calls:
        tool_name = tc.function.name
        if tool_name == "suggest_ssh_command":
            command_suggested = True
            args = json.loads(tc.function.arguments)
            card_data = {
                "command": args.get("command", ""),
                "server": args.get("server", ""),
                "explanation": args.get("explanation", "")
            }
            yield f"\n[CMD_CARD]{json.dumps(card_data)}[/CMD_CARD]\n"

    if command_suggested:
        print("DEBUG: Ending loop")
        return

async def main():
    print("--- START STREAM ---")
    full_response = ""
    async for chunk in mock_stream():
        print(f"CHUNK: {repr(chunk)}")
        full_response += chunk
    print("--- END STREAM ---")
    print("\nFULL RESPONSE STRING:")
    print(repr(full_response))

if __name__ == "__main__":
    asyncio.run(main())
