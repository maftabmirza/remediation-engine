"""
Commands API Router

Provides endpoints for command validation and execution.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.models import User
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/commands", tags=["commands"])


class CommandValidateRequest(BaseModel):
    command: str
    server: str


@router.post("/validate")
async def validate_command(
    request: CommandValidateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Validate a command before execution.
    Returns safety assessment and risk level.
    """
    from app.services.command_validator import CommandValidator, ValidationResult
    
    try:
        validator = CommandValidator()
        
        # Detect OS type from server name
        os_type = "windows" if any(x in request.server.lower() for x in ['win', 'windows']) else "linux"
        
        # Validate command
        result = validator.validate_command(request.command, os_type)
        
        return {
            "result": result.result.value,
            "message": result.message,
            "risk_level": result.risk_level if hasattr(result, 'risk_level') else 'unknown'
        }
    except Exception as e:
        return {
            "result": "unknown",
            "message": f"Validation error: {str(e)}",
            "risk_level": "unknown"
        }
