"""
Phase 5 Chat API Extensions

Add these endpoints to app/routers/chat_api.py
"""

from app.services.slash_commands import get_registry as get_slash_registry
from app.services.chat_participants import get_registry as get_participant_registry
from app.services.context_variables import resolve_all_variables


@router.get("/commands")
async def list_slash_commands():
    """Get all available slash commands for autocomplete"""
    registry = get_slash_registry()
    commands = registry.get_all_commands()
    return {"commands": [cmd.to_dict() for cmd in commands]}


@router.get("/participants")
async def list_participants():
    """Get all available chat participants for autocomplete"""
    registry = get_participant_registry()
    participants = registry.get_all_participants()
    return {"participants": [p.to_dict() for p in participants]}


class SlashCommandRequest(BaseModel):
    session_id: str
    command: str
    server_id: Optional[str] = None
    alert_id: Optional[str] = None


@router.post("/command")
async def execute_slash_command(
    request: SlashCommandRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a slash command"""
    registry = get_slash_registry()
    parsed = registry.parse(request.command)
    
    if not parsed:
        raise HTTPException(status_code=400, detail="Unknown command")
    
    name = parsed.command.name
    args = parsed.args
    
    # Generate prompts based on command type
    prompts = {
        "/diagnose": f"Start a diagnostic investigation for: {args}",
        "/fix": f"Apply the following fix: {args}",
        "/explain": f"Explain: {args}",
        "/plan": f"Plan action: {args or 'show'}",
        "/rollback": f"Rollback changes: {args or 'latest'}",
        "/spawn": f"Spawn background agent: {args}",
        "/hq": "Show Agent HQ status"
    }
    
    if name == "/help":
        commands = registry.get_all_commands()
        help_text = "**Available Commands:**\n\n"
        for cmd in commands:
            help_text += f"- **{cmd.name}** {cmd.args_pattern}\n  {cmd.description}\n  Example: `{cmd.example}`\n\n"
        return {"command_executed": "/help", "response": help_text, "create_message": True}
    
    prompt = prompts.get(name, f"Execute: {request.command}")
    return {"command_executed": name, "prompt": prompt, "success": True}
