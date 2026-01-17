"""
Scheduler Pydantic Schemas

Request/response models for the scheduler API endpoints.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from croniter import croniter


class ScheduledJobCreate(BaseModel):
    """Request model for creating a new scheduled job."""
    runbook_id: UUID
    name: str = Field(..., max_length=255, description="Unique name for this schedule")
    description: Optional[str] = None
    
    # Schedule Configuration
    schedule_type: str = Field(..., description="'cron', 'interval', or 'date'")
    cron_expression: Optional[str] = Field(None, description="Cron expression (e.g., '0 2 * * *')")
    interval_seconds: Optional[int] = Field(None, ge=60, description="Interval in seconds (min 60)")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    timezone: str = Field(default="UTC", description="IANA timezone name")
    
    # Execution Configuration
    target_server_id: Optional[UUID] = None
    execution_params: Optional[Dict[str, Any]] = None
    max_instances: int = Field(default=1, ge=1, le=10)
    misfire_grace_time: int = Field(default=300, ge=0, le=3600)
    
    enabled: bool = True
    
    @field_validator('schedule_type')
    @classmethod
    def validate_schedule_type(cls, v):
        if v not in ['cron', 'interval', 'date']:
            raise ValueError("schedule_type must be 'cron', 'interval', or 'date'")
        return v
    
    @model_validator(mode='after')
    def validate_schedule_fields(self):
        if self.schedule_type == 'cron':
            if not self.cron_expression:
                raise ValueError("cron_expression is required for cron schedules")
            if not croniter.is_valid(self.cron_expression):
                raise ValueError(f"Invalid cron expression: {self.cron_expression}")
        elif self.schedule_type == 'interval' and not self.interval_seconds:
            raise ValueError("interval_seconds is required for interval schedules")
        elif self.schedule_type == 'date' and not self.start_date:
            raise ValueError("start_date is required for date schedules")
        return self
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "runbook_id": "3df2e7bf-a5f0-4df1-b324-7734ffce4c83",
                "name": "Daily DB Cleanup",
                "description": "Clean up old records every day at 2 AM",
                "schedule_type": "cron",
                "cron_expression": "0 2 * * *",
                "timezone": "America/New_York",
                "enabled": True
            }
        }
    )


class ScheduledJobUpdate(BaseModel):
    """Request model for updating a scheduled job."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = Field(None, ge=60)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    timezone: Optional[str] = None
    
    target_server_id: Optional[UUID] = None
    execution_params: Optional[Dict[str, Any]] = None
    max_instances: Optional[int] = Field(None, ge=1, le=10)
    misfire_grace_time: Optional[int] = Field(None, ge=0, le=3600)
    
    enabled: Optional[bool] = None


class ScheduledJobResponse(BaseModel):
    """Response model for scheduled job details."""
    id: UUID
    runbook_id: UUID
    runbook_name: Optional[str] = None
    name: str
    description: Optional[str]
    
    schedule_type: str
    cron_expression: Optional[str]
    interval_seconds: Optional[int]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    timezone: str
    
    target_server_id: Optional[UUID]
    server_hostname: Optional[str] = None
    execution_params: Optional[Dict[str, Any]]
    max_instances: int
    misfire_grace_time: int
    
    enabled: bool
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    next_run_at: Optional[datetime]
    run_count: int
    failure_count: int
    
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ScheduleExecutionHistoryResponse(BaseModel):
    """Response model for schedule execution history."""
    id: UUID
    scheduled_job_id: UUID
    runbook_execution_id: Optional[UUID]
    
    scheduled_at: datetime
    executed_at: Optional[datetime]
    completed_at: Optional[datetime]
    status: str
    error_message: Optional[str]
    duration_ms: Optional[int]
    
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SchedulerStatsResponse(BaseModel):
    """Response model for scheduler statistics."""
    total_schedules: int
    enabled_schedules: int
    disabled_schedules: int
    total_executions_today: int
    successful_executions_today: int
    failed_executions_today: int
    next_scheduled_run: Optional[datetime]
    scheduler_running: bool
