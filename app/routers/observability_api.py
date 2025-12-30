"""
Observability Query API

REST API for AI-powered natural language observability queries.
Translates natural language questions into LogQL, TraceQL, and PromQL,
executes queries across multiple backends, and returns unified results.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
import logging

from app.database import get_db
from app.models_application import ApplicationProfile, GrafanaDatasource
from app.schemas_observability import (
    ObservabilityQueryRequest,
    ObservabilityQueryResponse,
    QueryTranslationResponse,
    QueryIntentResponse,
    LogsResultResponse,
    TracesResultResponse,
    MetricsResultResponse,
    LogEntryResponse,
    TraceResponse,
    MetricValueResponse,
    TranslatedQueryResponse
)
from app.services.observability_orchestrator import get_observability_orchestrator
from app.services.query_intent_parser import get_intent_parser
from app.services.query_translator import get_query_translator
from app.services.query_response_formatter import get_response_formatter, FormattedResponse
from app.services.query_cache import get_query_cache
from app.services.auth_service import get_current_user
from app.models import User

router = APIRouter(
    prefix="/api/observability",
    tags=["observability"]
)

logger = logging.getLogger(__name__)


# ============================================================================
# POST /api/observability/query - Execute Natural Language Query
# ============================================================================

@router.post("/query", response_model=ObservabilityQueryResponse)
async def query_observability(
    request: ObservabilityQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Execute a natural language observability query.

    Translates the natural language query into LogQL, TraceQL, and PromQL,
    executes queries across Loki, Tempo, and Prometheus in parallel,
    and returns unified results.

    **Example queries:**
    - "Show me error logs in the last hour"
    - "What's the error rate for my-app?"
    - "Show slow traces in the last 30 minutes"
    - "What's the P95 latency?"
    - "Is the application healthy?"
    """
    logger.info(f"Observability query from user {current_user.username}: {request.query}")

    # Get application context if provided
    app_context = None
    if request.application_id:
        profile = db.query(ApplicationProfile).filter(
            ApplicationProfile.app_id == request.application_id
        ).first()

        if profile:
            # Build context from profile
            translator = get_query_translator()
            app_context = translator.build_context_from_profile({
                "service_mappings": profile.service_mappings,
                "default_metrics": profile.default_metrics,
                "architecture_type": profile.architecture_type
            })

    # Get orchestrator and execute query
    orchestrator = get_observability_orchestrator()
    result = await orchestrator.query(request.query, app_context)

    # Convert to response schema
    intent_response = QueryIntentResponse(
        intent_type=result.intent.intent_type,
        confidence=result.intent.confidence,
        requires_logs=result.intent.requires_logs,
        requires_traces=result.intent.requires_traces,
        requires_metrics=result.intent.requires_metrics,
        application_name=result.intent.application_name,
        service_name=result.intent.service_name,
        time_range=result.intent.time_range,
        log_level=result.intent.log_level
    )

    # Convert logs results
    logs_responses = []
    for logs_result in result.logs_results:
        log_entries = [
            LogEntryResponse(
                timestamp=entry.timestamp,
                line=entry.line,
                labels=entry.labels
            )
            for entry in logs_result.entries
        ]
        logs_responses.append(LogsResultResponse(
            entries=log_entries,
            total_count=logs_result.total_count,
            query=logs_result.query,
            time_range=logs_result.time_range
        ))

    # Convert traces results
    traces_responses = []
    for traces_result in result.traces_results:
        trace_items = [
            TraceResponse(
                trace_id=trace.trace_id,
                root_service_name=trace.root_service_name,
                root_trace_name=trace.root_trace_name,
                start_time_unix_nano=trace.start_time_unix_nano,
                duration_ms=trace.duration_ms
            )
            for trace in traces_result.traces
        ]
        traces_responses.append(TracesResultResponse(
            traces=trace_items,
            total_count=traces_result.total_count,
            query=traces_result.query,
            time_range=traces_result.time_range
        ))

    # Convert metrics results
    metrics_responses = []
    for metrics_result in result.metrics_results:
        metric_values = [
            MetricValueResponse(timestamp=v["timestamp"], value=v["value"])
            for v in metrics_result.values
        ]
        metrics_responses.append(MetricsResultResponse(
            metric_name=metrics_result.metric_name,
            query=metrics_result.query,
            value=metrics_result.value,
            values=metric_values,
            time_range=metrics_result.time_range
        ))

    return ObservabilityQueryResponse(
        original_query=result.original_query,
        intent=intent_response,
        logs_results=logs_responses,
        traces_results=traces_responses,
        metrics_results=metrics_responses,
        total_logs=result.total_logs,
        total_traces=result.total_traces,
        total_metrics=result.total_metrics,
        execution_time_ms=result.execution_time_ms,
        backends_queried=result.backends_queried,
        errors=result.errors
    )


# ============================================================================
# POST /api/observability/translate - Debug: Show Query Translation
# ============================================================================

@router.post("/translate", response_model=QueryTranslationResponse)
async def translate_query(
    request: ObservabilityQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Translate a natural language query to observability query languages (debug endpoint).

    Shows how the natural language query is translated into LogQL, TraceQL,
    and PromQL without executing the queries. Useful for debugging and
    understanding query translation.
    """
    logger.info(f"Query translation request: {request.query}")

    # Get application context if provided
    app_context = None
    if request.application_id:
        profile = db.query(ApplicationProfile).filter(
            ApplicationProfile.app_id == request.application_id
        ).first()

        if profile:
            translator = get_query_translator()
            app_context = translator.build_context_from_profile({
                "service_mappings": profile.service_mappings,
                "default_metrics": profile.default_metrics,
                "architecture_type": profile.architecture_type
            })

    # Parse intent
    parser = get_intent_parser()
    intent = parser.parse(request.query)

    # Override time range if provided
    if request.time_range:
        intent.time_range = request.time_range

    # Translate query
    translator = get_query_translator()
    translation = translator.translate(intent, app_context)

    # Convert to response
    intent_response = QueryIntentResponse(
        intent_type=intent.intent_type,
        confidence=intent.confidence,
        requires_logs=intent.requires_logs,
        requires_traces=intent.requires_traces,
        requires_metrics=intent.requires_metrics,
        application_name=intent.application_name,
        service_name=intent.service_name,
        time_range=intent.time_range,
        log_level=intent.log_level
    )

    logql_responses = [
        TranslatedQueryResponse(
            query_language=q.query_language,
            query=q.query,
            time_range=q.time_range
        )
        for q in translation.logql_queries
    ]

    traceql_responses = [
        TranslatedQueryResponse(
            query_language=q.query_language,
            query=q.query,
            time_range=q.time_range
        )
        for q in translation.traceql_queries
    ]

    promql_responses = [
        TranslatedQueryResponse(
            query_language=q.query_language,
            query=q.query,
            time_range=q.time_range
        )
        for q in translation.promql_queries
    ]

    return QueryTranslationResponse(
        original_query=request.query,
        intent=intent_response,
        logql_queries=logql_responses,
        traceql_queries=traceql_responses,
        promql_queries=promql_responses
    )


# ============================================================================
# GET /api/observability/examples - Get Example Queries
# ============================================================================

@router.get("/examples")
async def get_example_queries(
    current_user: User = Depends(get_current_user)
):
    """
    Get example natural language queries.

    Returns a list of example queries organized by category to help users
    understand what types of questions they can ask.
    """
    return {
        "categories": {
            "logs": {
                "description": "Query application logs",
                "examples": [
                    "Show me error logs in the last hour",
                    "Find warning logs for my-app",
                    "Show logs containing 'database timeout'",
                    "Get recent logs with status 500"
                ]
            },
            "traces": {
                "description": "Query distributed traces",
                "examples": [
                    "Show slow traces in the last 30 minutes",
                    "Find traces with errors",
                    "Show traces for the checkout service",
                    "Get traces with 500 status code"
                ]
            },
            "metrics": {
                "description": "Query application metrics",
                "examples": [
                    "What's the error rate?",
                    "Show CPU usage",
                    "What's the P95 latency?",
                    "How many requests per second?"
                ]
            },
            "health": {
                "description": "Check application health",
                "examples": [
                    "Is the application healthy?",
                    "What's the uptime?",
                    "Show service availability",
                    "Is my-app running?"
                ]
            },
            "performance": {
                "description": "Analyze performance",
                "examples": [
                    "Why is the app slow?",
                    "Show response time trends",
                    "What's the P99 latency?",
                    "Find slow requests"
                ]
            },
            "errors": {
                "description": "Investigate errors",
                "examples": [
                    "Show recent errors",
                    "What's causing 500 errors?",
                    "Count errors in the last hour",
                    "Find exceptions in my-app"
                ]
            }
        }
    }


# ============================================================================
# POST /api/observability/query/formatted - Execute Query with Formatting
# ============================================================================

@router.post("/query/formatted", response_model=FormattedResponse)
async def query_observability_formatted(
    request: ObservabilityQueryRequest,
    use_cache: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Execute a natural language query and return formatted human-readable results.

    This endpoint provides AI-powered formatting of query results with:
    - Executive summary
    - Key insights with severity levels
    - Recommendations
    - Quick stats

    Supports caching for improved performance.
    """
    logger.info(f"Formatted query from user {current_user.username}: {request.query}")

    # Get application context
    app_context = None
    if request.application_id:
        profile = db.query(ApplicationProfile).filter(
            ApplicationProfile.app_id == request.application_id
        ).first()

        if profile:
            translator = get_query_translator()
            app_context = translator.build_context_from_profile({
                "service_mappings": profile.service_mappings,
                "default_metrics": profile.default_metrics,
                "architecture_type": profile.architecture_type
            })

    # Check cache
    cache = get_query_cache()
    if use_cache:
        cached_result = cache.get(request.query, app_context)
        if cached_result is not None:
            logger.info("Returning cached formatted result")
            return cached_result

    # Execute query
    orchestrator = get_observability_orchestrator()
    result = await orchestrator.query(request.query, app_context)

    # Format response
    formatter = get_response_formatter()
    formatted = formatter.format(result)

    # Save to database for persistence
    try:
        from app.models_chat import InquiryResult, InquirySession
        
        # Link to session and update title if needed
        if request.session_id:
            session = db.query(InquirySession).filter(
                InquirySession.id == request.session_id,
                InquirySession.user_id == current_user.id
            ).first()
            
            if session:
                # Set title from first query if not already set
                if not session.title:
                    # Use first 50 chars of query as title
                    session.title = request.query[:50] + ('...' if len(request.query) > 50 else '')
                    db.add(session)
        
        inquiry_result = InquiryResult(
            user_id=current_user.id,
            session_id=request.session_id,
            query=request.query,
            result_json=formatted.dict() if hasattr(formatted, 'dict') else None,
            summary=formatted.summary if hasattr(formatted, 'summary') else None,
            intent_type=formatted.intent.get('intent_type') if hasattr(formatted, 'intent') and formatted.intent else None,
            execution_time_ms=formatted.stats.get('execution_time_ms') if hasattr(formatted, 'stats') and formatted.stats else None
        )
        db.add(inquiry_result)
        db.commit()
        logger.info(f"Saved inquiry result with ID: {inquiry_result.id}")
    except Exception as e:
        logger.error(f"Failed to save inquiry result: {e}")
        db.rollback()

    # Cache result
    if use_cache:
        cache.set(request.query, formatted, app_context)

    return formatted


# ============================================================================
# GET /api/observability/cache/stats - Get Cache Statistics
# ============================================================================

@router.get("/cache/stats")
async def get_cache_stats(
    current_user: User = Depends(get_current_user)
):
    """
    Get query cache statistics.

    Returns cache hit rate, size, and other metrics.
    """
    cache = get_query_cache()
    return cache.get_stats()


# ============================================================================
# DELETE /api/observability/cache - Clear Cache
# ============================================================================

@router.delete("/cache")
async def clear_cache(
    current_user: User = Depends(get_current_user)
):
    """
    Clear the query cache.

    Requires authentication. Useful for debugging or forcing fresh queries.
    """
    cache = get_query_cache()
    cache.clear()
    return {"message": "Cache cleared successfully"}


# ============================================================================
# GET /api/observability/inquiry/history - Get Inquiry History
# ============================================================================

@router.get("/inquiry/history")
async def get_inquiry_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get inquiry history for the current user.

    Returns the most recent inquiry results with their queries and summaries.
    """
    from app.models_chat import InquiryResult
    
    results = db.query(InquiryResult).filter(
        InquiryResult.user_id == current_user.id
    ).order_by(InquiryResult.created_at.desc()).limit(limit).all()
    
    return {
        "items": [
            {
                "id": str(r.id),
                "query": r.query,
                "summary": r.summary,
                "intent_type": r.intent_type,
                "execution_time_ms": r.execution_time_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in results
        ],
        "total": len(results)
    }


# ============================================================================
# GET /api/observability/inquiry/result/{id} - Get Single Inquiry Result
# ============================================================================

@router.get("/inquiry/result/{inquiry_id}")
async def get_inquiry_result(
    inquiry_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific inquiry result by ID.

    Returns the full result including the result_json for data output display.
    """
    from app.models_chat import InquiryResult
    
    result = db.query(InquiryResult).filter(
        InquiryResult.id == inquiry_id,
        InquiryResult.user_id == current_user.id
    ).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Inquiry result not found")
    
    return {
        "id": str(result.id),
        "query": result.query,
        "summary": result.summary,
        "intent_type": result.intent_type,
        "execution_time_ms": result.execution_time_ms,
        "result_json": result.result_json,
        "created_at": result.created_at.isoformat() if result.created_at else None
    }


# ============================================================================
# GET /api/observability/inquiry/sessions - List Inquiry Sessions
# ============================================================================

@router.get("/inquiry/sessions")
async def list_inquiry_sessions(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List inquiry sessions for the current user.

    Returns the most recent sessions with their titles and message counts.
    """
    from app.models_chat import InquirySession, InquiryResult
    from sqlalchemy import func
    
    # Get sessions with message count
    sessions = db.query(
        InquirySession,
        func.count(InquiryResult.id).label('message_count')
    ).outerjoin(InquiryResult).filter(
        InquirySession.user_id == current_user.id
    ).group_by(InquirySession.id).order_by(
        InquirySession.updated_at.desc()
    ).limit(limit).all()
    
    return {
        "items": [
            {
                "id": str(s.InquirySession.id),
                "title": s.InquirySession.title or "New Session",
                "message_count": s.message_count,
                "created_at": s.InquirySession.created_at.isoformat() if s.InquirySession.created_at else None,
                "updated_at": s.InquirySession.updated_at.isoformat() if s.InquirySession.updated_at else None
            }
            for s in sessions
        ],
        "total": len(sessions)
    }


# ============================================================================
# POST /api/observability/inquiry/sessions - Create New Session
# ============================================================================

@router.post("/inquiry/sessions")
async def create_inquiry_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new inquiry session.

    Returns the new session with its ID.
    """
    from app.models_chat import InquirySession
    
    session = InquirySession(
        user_id=current_user.id,
        title=None  # Will be set from first query
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    logger.info(f"Created inquiry session {session.id} for user {current_user.username}")
    
    return {
        "id": str(session.id),
        "title": session.title or "New Session",
        "created_at": session.created_at.isoformat() if session.created_at else None
    }


# ============================================================================
# GET /api/observability/inquiry/sessions/{id} - Get Session with Messages
# ============================================================================

@router.get("/inquiry/sessions/{session_id}")
async def get_inquiry_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific inquiry session with all its messages.

    Returns the session details and all query results.
    """
    from app.models_chat import InquirySession, InquiryResult
    
    session = db.query(InquirySession).filter(
        InquirySession.id == session_id,
        InquirySession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    results = db.query(InquiryResult).filter(
        InquiryResult.session_id == session_id
    ).order_by(InquiryResult.created_at.asc()).all()
    
    return {
        "id": str(session.id),
        "title": session.title or "New Session",
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "messages": [
            {
                "id": str(r.id),
                "query": r.query,
                "summary": r.summary,
                "intent_type": r.intent_type,
                "result_json": r.result_json,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in results
        ]
    }


# ============================================================================
# DELETE /api/observability/inquiry/sessions/{id} - Delete Session
# ============================================================================

@router.delete("/inquiry/sessions/{session_id}")
async def delete_inquiry_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an inquiry session and all its messages.
    """
    from app.models_chat import InquirySession
    
    session = db.query(InquirySession).filter(
        InquirySession.id == session_id,
        InquirySession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db.delete(session)
    db.commit()
    
    return {"message": "Session deleted successfully"}
