
import asyncio
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models_agent import AgentSession, AgentStep, AgentStatus, StepStatus
from sqlalchemy import text

def analyze_failures():
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(hours=3)
        print(f"Analyzing failures since: {since}")
        
        # 1. Failed Sessions
        failed_sessions = db.query(AgentSession).filter(
            AgentSession.created_at >= since,
            AgentSession.status.in_([AgentStatus.FAILED.value, AgentStatus.STOPPED.value])
        ).all()
        
        print("\n--- Failed/Stopped Sessions ---")
        for s in failed_sessions:
            print(f"Session {s.id} | Status: {s.status} | Goal: {s.goal[:50]}...")
            if s.error_message:
                print(f"  Error: {s.error_message}")
            
            # Get last steps
            last_step = db.query(AgentStep).filter(
                AgentStep.agent_session_id == s.id
            ).order_by(AgentStep.step_number.desc()).first()
            
            if last_step:
                print(f"  Last Step {last_step.step_number} ({last_step.step_type}): {last_step.status}")
                if last_step.output:
                    print(f"  Output Snippet: {last_step.output[:200]}")

        # 2. Failed Steps in otherwise active/completed sessions (if any)
        failed_steps = db.query(AgentStep).join(AgentSession).filter(
            AgentStep.created_at >= since,
            AgentStep.status == StepStatus.FAILED.value
        ).all()
        
        print("\n--- Individual Failed Steps ---")
        for step in failed_steps:
            print(f"Session {step.agent_session_id} | Step {step.step_number} | Type: {step.step_type}")
            print(f"  Content: {step.content}")
            print(f"  Output: {step.output[:200]}")

    finally:
        db.close()

if __name__ == "__main__":
    analyze_failures()
