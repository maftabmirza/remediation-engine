import logging
import uuid
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal, get_db
from app.models_agent_pool import AgentPool, AgentTask
from app.models_agent import AgentSession
from app.models_revive import AISession
from app.workers.background_agent import BackgroundAgentRunner

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    _instance = None
    _active_tasks: Dict[UUID, asyncio.Task] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentOrchestrator, cls).__new__(cls)
        return cls._instance

    def create_pool(self, db: Session, session_id: UUID, name: str, max_concurrent: int = 3) -> AgentPool:
        """Create a new agent pool for an AI session."""
        pool = AgentPool(
            session_id=session_id,
            name=name,
            max_concurrent_agents=max_concurrent
        )
        db.add(pool)
        db.commit()
        db.refresh(pool)
        return pool

    def get_pool(self, db: Session, pool_id: UUID) -> Optional[AgentPool]:
        return db.query(AgentPool).filter(AgentPool.id == pool_id).first()

    def get_pool_by_session(self, db: Session, session_id: UUID) -> Optional[AgentPool]:
        # Assume one pool per session for now or get default
        return db.query(AgentPool).filter(AgentPool.session_id == session_id).first()

    async def spawn_agent(
        self, 
        pool_id: UUID, 
        goal: str, 
        agent_type: str = "background",
        priority: int = 10,
        context_variables: Dict = None,
        auto_iterate: bool = False,
        max_iterations: int = 5
    ) -> AgentTask:
        """
        Spawn a new agent task.
        If slot available, runs immediately. Otherwise queues it.
        """
        # 1. Create Task Record
        db = SessionLocal()
        try:
            task = AgentTask(
                pool_id=pool_id,
                goal=goal,
                agent_type=agent_type,
                priority=priority,
                status="queued",
                auto_iterate=auto_iterate,
                max_iterations=max_iterations
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            task_id = task.id
        finally:
            db.close()

        # 2. Try to schedule
        await self._schedule_pool(pool_id)
        
        # Reload to get updated status
        db = SessionLocal()
        try:
           task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
           return task
        finally:
            db.close()

    async def _schedule_pool(self, pool_id: UUID):
        """Check pool concurrency and launch waiting tasks."""
        db = SessionLocal()
        try:
            pool = db.query(AgentPool).filter(AgentPool.id == pool_id).first()
            if not pool:
                return

            # Count active tasks
            active_count = db.query(AgentTask).filter(
                AgentTask.pool_id == pool_id,
                AgentTask.status.in_(["running"])
            ).count()

            if active_count >= pool.max_concurrent_agents:
                return

            # Get next queued task
            slots_available = pool.max_concurrent_agents - active_count
            
            pending_tasks = db.query(AgentTask).filter(
                AgentTask.pool_id == pool_id,
                AgentTask.status == "queued"
            ).order_by(AgentTask.priority.desc(), AgentTask.created_at.asc()).limit(slots_available).all()

            for task in pending_tasks:
                await self._launch_task(task.id)

        finally:
            db.close()

    async def _launch_task(self, task_id: UUID):
        """Launch a specific task in background"""
        db = SessionLocal()
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if not task:
                return

            task.status = "running"
            task.started_at = datetime.utcnow()
            db.commit()
            
            # Start asyncio Task
            runner = BackgroundAgentRunner(task_id=task.id)
            async_task = asyncio.create_task(runner.run())
            
            self._active_tasks[task.id] = async_task
            
            # Add cleanup callback
            def cleanup(future):
                if task.id in self._active_tasks:
                    del self._active_tasks[task.id]
                # Trigger schedule next
                asyncio.create_task(self._schedule_pool(task.pool_id))
            
            async_task.add_done_callback(cleanup)
            
            logger.info(f"Launched agent task {task.id}")

        except Exception as e:
            logger.error(f"Failed to launch task {task_id}: {e}")
            task.status = "failed"
            db.commit()
        finally:
            db.close()

    async def stop_agent(self, task_id: UUID) -> bool:
        """Stop a running agent"""
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            return True
        return False

    def get_active_tasks(self, pool_id: UUID) -> List[AgentTask]:
        db = SessionLocal()
        try:
             return db.query(AgentTask).filter(
                AgentTask.pool_id == pool_id,
                AgentTask.status.in_(["running", "queued"])
            ).all()
        finally:
            db.close()
