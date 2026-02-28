"""
AI Helper Database Models - DEPRECATED
This file is kept for backwards compatibility. New code should import from app.models_ai.
"""
from app.models_ai import AISession, AIMessage

# Re-export for compatibility
__all__ = ["AISession", "AIMessage"]
