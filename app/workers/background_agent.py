import logging
import traceback
import asyncio
from datetime import datetime, timezone
from uuid import UUID

from app.database import SessionLocal
from app.models_agent_pool import AgentTask
from app.models_agent import AgentSession
from app.models_revive import AISession, AIMessage
from app.models import User, LLMProvider
from app.services.agentic.native_agent import NativeToolAgent

logger = logging.getLogger(__name__)

class BackgroundAgentRunner:
    def __init__(self, task_id: UUID):
        self.task_id = task_id

    async def run(self):
        """Execute the agent task."""
        db = SessionLocal()
        try:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            if not task:
                logger.error(f"Task {self.task_id} not found")
                return

            pool = task.pool
            ai_session = db.query(AISession).filter(AISession.id == pool.session_id).first()
            user = ai_session.user if ai_session else None

            if not user:
                # Fallbck to first admin or error
                user = db.query(User).first() # Dangerous fallback?
            
            # Create Agent Session if not exists
            if not task.agent_session_id:
                agent_session = AgentSession(
                    chat_session_id=pool.session_id,
                    user_id=user.id,
                    goal=task.goal,
                    agent_type="background",
                    pool_id=pool.id,
                    status="executing",
                    worktree_path=task.worktree_path
                )
                db.add(agent_session)
                db.commit()
                db.refresh(agent_session)
                task.agent_session_id = agent_session.id
                db.commit()
            else:
                agent_session = db.query(AgentSession).filter(AgentSession.id == task.agent_session_id).first()
                agent_session.status = "executing"
                db.commit()

            # Initialize NativeToolAgent
            # We need an LLMProvider. Try to find the default one or from user config.
            provider = db.query(LLMProvider).filter(LLMProvider.is_active == True).first()
            if not provider:
                raise Exception("No active LLM provider found")
            
            # Helper for iteration logging
            from app.services.iteration_service import IterationService
            from app.services.agentic.tools.registry import create_background_registry
            import re
            
            iteration_service = IterationService(db)
            current_iteration = 0
            
            def log_iteration(tool_name: str, args: Dict, result: str):
                nonlocal current_iteration
                current_iteration += 1
                
                # Extract exit code if possible (from execute_server_command output)
                exit_code = 0 
                if tool_name == "execute_server_command":
                    match = re.search(r"Exit Code: (\d+)", result)
                    if match:
                        exit_code = int(match.group(1))
                
                iteration_service.record_iteration(
                    agent_task_id=task.id,
                    iteration_number=current_iteration,
                    command=args.get("command", f"Call {tool_name}"),
                    output=result,
                    exit_code=exit_code
                )
                logger.info(f"Recorded iteration {current_iteration} for task {task.id}")

            agent = NativeToolAgent(
                db=db,
                provider=provider,
                # alert=None, # Background agents might work on alerts later
                initial_messages=[], # Start fresh for now
                on_tool_call_complete=log_iteration,
                registry_factory=create_background_registry
            )

            # Execution Loop
            response = await agent.run(task.goal)

            # Update status based on response
            if response.error:
                task.status = "failed"
                agent_session.status = "failed"
                agent_session.error_message = response.error
            else:
                task.status = "completed"
                agent_session.status = "completed"
                agent_session.summary = response.content

            task.completed_at = datetime.now(timezone.utc)
            agent_session.completed_at = datetime.now(timezone.utc)
            db.commit()

            # Log completion to Chat Session
            completion_msg = f"**Background Agent Completed**\nGoal: {task.goal}\n\nResult: {response.content}"
            chat_msg = AIMessage(
                session_id=pool.session_id,
                role="assistant",
                content=completion_msg,
                metadata_json={"task_id": str(task.id), "agent_type": "background"}
            )
            db.add(chat_msg)
            db.commit()

        except asyncio.CancelledError:
            logger.info(f"Task {self.task_id} cancelled")
            # Update status? DB session might be closed or tricky in cancel handler
            # We trust Orchestrator cleanup or next run to fix status if stuck
        except Exception as e:
            logger.error(f"Error running task {self.task_id}: {e}")
            logger.error(traceback.format_exc())
            # Try to update status if DB still alive
            try:
                task.status = "failed"
                if 'agent_session' in locals() and agent_session:
                     agent_session.status = "failed"
                     agent_session.error_message = str(e)
                db.commit()
            except:
                pass
        finally:
            db.close()
