"""
Unified PII and secret detection service.
"""
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID
import logging

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from presidio_analyzer import RecognizerResult

from app.models.pii_models import PIIDetectionConfig, PIIDetectionLog, SecretBaseline
from app.schemas.pii_schemas import (
    DetectionRequest,
    DetectionResponse,
    DetectionResult,
    RedactionRequest,
    RedactionResponse,
    PIIConfigResponse,
    PIIConfigUpdate,
    DetectionLogListResponse,
    DetectionLogQuery,
    DetectionStatsResponse,
    EntityListResponse,
    PluginListResponse
)
from app.services.presidio_service import PresidioService
from app.services.secret_detection_service import SecretDetectionService
from app.services.detection_merger import DetectionMerger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.pii_whitelist_service import PIIWhitelistService


logger = logging.getLogger(__name__)


class PIIService:
    """
    Unified service for PII and secret detection.
    
    Orchestrates Presidio and detect-secrets, merges results,
    logs detections, and manages configuration.
    
    Supports async context manager protocol for proper session cleanup.
    """
    
    # Default allowed entities (whitelist) - Presidio built-in only
    # Explicitly excluding: DATE_TIME, NRP (Nationality/Religion/Political), URL
    # Note: CRYPTO excluded due to OverflowError bug in Presidio's CryptoRecognizer on long base58 strings
    DEFAULT_ENTITIES = [
        "EMAIL_ADDRESS", 
        "PHONE_NUMBER", 
        "PERSON", 
        "CREDIT_CARD", 
        "IP_ADDRESS", 
        "US_SSN",
        "US_PASSPORT",
        "US_DRIVER_LICENSE",
        "IBAN_CODE",
        "US_BANK_NUMBER",
        # "CRYPTO",  # Disabled - causes OverflowError on long random strings
        "MEDICAL_LICENSE",
    ]
    
    def __init__(
        self,
        db: AsyncSession,
        presidio_service: PresidioService,
        secret_service: SecretDetectionService,
        owns_session: bool = False,
        whitelist_service: Optional['PIIWhitelistService'] = None
    ):
        """
        Initialize PII service.
        
        Args:
            db: Database session
            presidio_service: Presidio service instance
            secret_service: Secret detection service instance
            owns_session: If True, close the session when this service is closed
            whitelist_service: Optional whitelist service for false positive filtering
        """
        self.db = db
        self.presidio = presidio_service
        self.secrets = secret_service
        self.merger = DetectionMerger()
        self._owns_session = owns_session
        self.whitelist_service = whitelist_service
    
    async def close(self):
        """Close the database session if this service owns it."""
        if self._owns_session and self.db:
            try:
                await self.db.close()
            except Exception as e:
                logger.debug(f"Error closing PIIService session: {e}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close session if owned."""
        await self.close()
        return False
    
    async def detect(
        self,
        text: str,
        source_type: str,
        source_id: Optional[str] = None,
        engines: Optional[List[str]] = None,
        entity_types: Optional[List[str]] = None
    ) -> DetectionResponse:
        """
        Detect PII and secrets in text.
        
        Args:
            text: Text to analyze
            source_type: Type of source (runbook_output, llm_response, etc.)
            source_id: ID of source record
            engines: Engines to use (presidio, detect_secrets)
            entity_types: Specific entity types to detect
            
        Returns:
            Detection response with all detections
        """
        start_time = time.time()
        
        # Default to both engines
        if engines is None:
            engines = ['presidio', 'detect_secrets']
            
        # Use default entities if not specified
        if entity_types is None:
            entity_types = self.DEFAULT_ENTITIES
        
        presidio_results = []
        secret_results = []
        
        # Run Presidio detection
        if 'presidio' in engines:
            try:
                analyzer_results = self.presidio.analyze(
                    text=text,
                    entities=entity_types
                )
                
                # Convert to dict format
                for result in analyzer_results:
                    presidio_results.append({
                        'entity_type': result.entity_type,
                        'value': text[result.start:result.end],
                        'start': result.start,
                        'end': result.end,
                        'confidence': result.score,
                        'context': self._extract_context(text, result.start, result.end)
                    })
                    
            except Exception as e:
                logger.error(f"Error running Presidio detection: {e}", exc_info=True)
        
        # Run detect-secrets detection
        if 'detect_secrets' in engines:
            try:
                secret_results = self.secrets.scan_text(text)
                
                # Add context to secret results
                for result in secret_results:
                    # Estimate positions if not provided
                    if result.get('start', 0) == 0:
                        # Try to find the secret in text
                        # This is a simplified approach
                        result['context'] = text[:100] + '...'
                    else:
                        result['context'] = self._extract_context(
                            text,
                            result['start'],
                            result['end']
                        )
                        
            except Exception as e:
                logger.error(f"Error running secret detection: {e}", exc_info=True)
        
        # Merge and deduplicate results
        merged_results = self.merger.merge(presidio_results, secret_results)
        deduplicated_results = self.merger.deduplicate(merged_results)
        
        # Filter out whitelisted items
        if self.whitelist_service:
            logger.info(f"🔍 PII Whitelist Check: Checking {len(deduplicated_results)} detections against whitelist")
            filtered_results = []
            whitelist_hits = 0
            for detection in deduplicated_results:
                is_whitelisted = await self.whitelist_service.is_whitelisted(
                    text=detection['value'],
                    entity_type=detection['entity_type'],
                    scope='organization'
                )
                if not is_whitelisted:
                    filtered_results.append(detection)
                else:
                    whitelist_hits += 1
                    logger.info(f"✅ PII Whitelist Hit: Skipping '{detection['value'][:30]}...' (type={detection['entity_type']})")
            
            if whitelist_hits > 0:
                logger.info(f"🎯 PII Whitelist: Filtered out {whitelist_hits}/{len(deduplicated_results)} detections")
            deduplicated_results = filtered_results
        else:
            logger.warning("⚠️ PII Whitelist Service not available - no whitelist filtering applied")
        
        # Log detections
        for detection in deduplicated_results:
            await self.log_detection(
                detection=detection,
                source_type=source_type,
                source_id=source_id
            )
        
        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Convert to response format
        detection_results = [
            DetectionResult(**detection)
            for detection in deduplicated_results
        ]
        
        return DetectionResponse(
            detections=detection_results,
            detection_count=len(detection_results),
            processing_time_ms=processing_time_ms
        )
    
    async def redact(
        self,
        text: str,
        redaction_type: str = "mask",
        mask_char: str = "*",
        preserve_length: bool = False
    ) -> RedactionResponse:
        """
        Redact PII and secrets from text.
        
        Args:
            text: Text to redact
            redaction_type: Type of redaction (mask, hash, remove, tag)
            mask_char: Character for masking
            preserve_length: Whether to preserve original length
            
        Returns:
            Redaction response with redacted text
        """
        # First detect all PII/secrets
        detection_response = await self.detect(
            text=text,
            source_type="redaction_request",
            engines=['presidio', 'detect_secrets']
        )
        
        if not detection_response.detections:
            return RedactionResponse(
                original_length=len(text),
                redacted_text=text,
                redactions_applied=0,
                detections=[]
            )
        
        # Convert detections to Presidio format for anonymization
        analyzer_results = []
        for detection in detection_response.detections:
            result = RecognizerResult(
                entity_type=detection.entity_type,
                start=detection.start,
                end=detection.end,
                score=detection.confidence
            )
            analyzer_results.append(result)
        
        # Anonymize with Presidio - returns dict with 'text' and 'items'
        anonymize_result = self.presidio.anonymize(
            text=text,
            analyzer_results=analyzer_results,
            redaction_type=redaction_type,
            mask_char=mask_char
        )
        
        return RedactionResponse(
            original_length=len(text),
            redacted_text=anonymize_result["text"],
            redactions_applied=len(detection_response.detections),
            detections=detection_response.detections,
            items=anonymize_result["items"]
        )
    
    async def log_detection(
        self,
        detection: Dict[str, Any],
        source_type: str,
        source_id: Optional[str] = None
    ) -> None:
        """
        Log a detection to the database.
        
        Args:
            detection: Detection result dict
            source_type: Type of source
            source_id: ID of source record
        """
        try:
            # Hash the detected value
            value = detection.get('value', '')
            value_hash = hashlib.sha256(value.encode()).hexdigest()
            
            # Create log entry
            log_entry = PIIDetectionLog(
                entity_type=detection.get('entity_type'),
                detection_engine=detection.get('engine'),
                confidence_score=detection.get('confidence', 0.0),
                source_type=source_type,
                source_id=UUID(source_id) if source_id else None,
                context_snippet=detection.get('context', ''),
                position_start=detection.get('start', 0),
                position_end=detection.get('end', 0),
                was_redacted=True,  # Assume redacted by default
                redaction_type='mask',
                original_hash=value_hash
            )
            
            self.db.add(log_entry)
            await self.db.commit()
            
            logger.debug(f"Logged detection: {detection.get('entity_type')} from {source_type}")
            
        except Exception as e:
            logger.error(f"Error logging detection: {e}", exc_info=True)
            await self.db.rollback()
    
    async def get_config(self) -> PIIConfigResponse:
        """
        Get current PII detection configuration.
        
        Returns:
            Configuration response
        """
        # Get Presidio entities config
        presidio_entities = self.presidio.get_supported_entities()
        
        # Get detect-secrets plugins config
        secret_plugins = self.secrets.get_available_plugins()
        
        # TODO: Load actual config from database
        # For now, return defaults
        
        return PIIConfigResponse(
            presidio={
                'enabled': True,
                'entities': [
                    {
                        'entity_type': entity['name'],
                        'enabled': True,
                        'threshold': 0.7,
                        'redaction_type': 'mask'
                    }
                    for entity in presidio_entities[:5]  # Sample
                ]
            },
            detect_secrets={
                'enabled': True,
                'plugins': [
                    {
                        'plugin_name': plugin['name'],
                        'enabled': True,
                        'settings': {}
                    }
                    for plugin in secret_plugins[:5]  # Sample
                ]
            },
            global_settings={
                'log_detections': True,
                'auto_redact': True,
                'default_redaction_type': 'mask'
            }
        )
    
    async def update_config(self, update: PIIConfigUpdate) -> PIIConfigResponse:
        """
        Update PII detection configuration.
        
        Args:
            update: Configuration updates
            
        Returns:
            Updated configuration
        """
        # TODO: Implement config persistence to database
        logger.info(f"Configuration update requested: {update}")
        
        return await self.get_config()
    
    @staticmethod
    def _extract_context(text: str, start: int, end: int, context_length: int = 30) -> str:
        """
        Extract context around a detection.
        
        Args:
            text: Full text
            start: Start position
            end: End position
            context_length: Characters before/after
            
        Returns:
            Context snippet with redacted value
        """
        # Get surrounding context
        context_start = max(0, start - context_length)
        context_end = min(len(text), end + context_length)
        
        # Build context with redacted value
        before = text[context_start:start]
        after = text[end:context_end]
        redacted_value = '[REDACTED]'
        
        context = f"...{before}{redacted_value}{after}..."
        
        return context.strip()
    
    async def get_logs(
        self,
        query: DetectionLogQuery
    ) -> DetectionLogListResponse:
        """
        Get detection logs with filtering and pagination.
        
        Args:
            query: Log query parameters
            
        Returns:
            Paginated list of logs
        """
        # Build query
        stmt = select(PIIDetectionLog)
        
        # Apply filters
        if query.entity_type:
            stmt = stmt.where(PIIDetectionLog.entity_type == query.entity_type)
        
        if query.engine:
            stmt = stmt.where(PIIDetectionLog.detection_engine == query.engine)
        
        if query.source_type:
            stmt = stmt.where(PIIDetectionLog.source_type == query.source_type)
        
        if query.start_date:
            stmt = stmt.where(PIIDetectionLog.detected_at >= query.start_date)
        
        if query.end_date:
            # inclusive end date
            end_date = query.end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            stmt = stmt.where(PIIDetectionLog.detected_at <= end_date)

        if query.q:
            search_term = f"%{query.q}%"
            stmt = stmt.where(
                or_(
                    PIIDetectionLog.context_snippet.ilike(search_term),
                    PIIDetectionLog.entity_type.ilike(search_term),
                    PIIDetectionLog.detection_engine.ilike(search_term),
                    PIIDetectionLog.source_type.ilike(search_term)
                )
            )

        # Optimize count query
        # Instead of subquery, use direct count if no filters are applied
        # Or use a simpler count that avoids loading all columns
        
        # Get total count
        count_stmt = select(func.count(PIIDetectionLog.id))
        
        # Apply same filters to count
        if query.entity_type:
            count_stmt = count_stmt.where(PIIDetectionLog.entity_type == query.entity_type)
        if query.engine:
            count_stmt = count_stmt.where(PIIDetectionLog.detection_engine == query.engine)
        if query.source_type:
            count_stmt = count_stmt.where(PIIDetectionLog.source_type == query.source_type)
        if query.start_date:
            count_stmt = count_stmt.where(PIIDetectionLog.detected_at >= query.start_date)
        if query.end_date:
            end_date = query.end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            count_stmt = count_stmt.where(PIIDetectionLog.detected_at <= end_date)
            
        if query.q:
            search_term = f"%{query.q}%"
            count_stmt = count_stmt.where(
                or_(
                    PIIDetectionLog.context_snippet.ilike(search_term),
                    PIIDetectionLog.entity_type.ilike(search_term),
                    PIIDetectionLog.detection_engine.ilike(search_term),
                    PIIDetectionLog.source_type.ilike(search_term)
                )
            )
            
        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0
        
        # Apply pagination
        stmt = stmt.order_by(desc(PIIDetectionLog.detected_at))
        stmt = stmt.offset((query.page - 1) * query.limit).limit(query.limit)
        
        # Execute query
        result = await self.db.execute(stmt)
        logs = result.scalars().all()
        
        # Calculate pages
        pages = (total + query.limit - 1) // query.limit
        
        return DetectionLogListResponse(
            logs=logs,
            total=total,
            page=query.page,
            limit=query.limit,
            pages=pages
        )
    
    async def get_stats(self, period: str = "7d") -> DetectionStatsResponse:
        """
        Get detection statistics.
        
        Args:
            period: Time period (7d, 30d, etc.)
            
        Returns:
            Statistics response
        """
        from datetime import timedelta
        
        # Parse period
        days = 7
        if period == "30d":
            days = 30
        elif period == "90d":
            days = 90
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            # Total detections
            total_stmt = select(func.count(PIIDetectionLog.id)).where(
                PIIDetectionLog.detected_at >= start_date
            )
            total_result = await self.db.execute(total_stmt)
            total_detections = total_result.scalar() or 0
            
            # By entity type
            by_type_stmt = select(
                PIIDetectionLog.entity_type,
                func.count(PIIDetectionLog.id)
            ).where(
                PIIDetectionLog.detected_at >= start_date
            ).group_by(PIIDetectionLog.entity_type)
            by_type_result = await self.db.execute(by_type_stmt)
            by_entity_type = {row[0]: row[1] for row in by_type_result}
            
            # By engine
            by_engine_stmt = select(
                PIIDetectionLog.detection_engine,
                func.count(PIIDetectionLog.id)
            ).where(
                PIIDetectionLog.detected_at >= start_date
            ).group_by(PIIDetectionLog.detection_engine)
            by_engine_result = await self.db.execute(by_engine_stmt)
            by_engine = {row[0]: row[1] for row in by_engine_result}
            
            # By source
            by_source_stmt = select(
                PIIDetectionLog.source_type,
                func.count(PIIDetectionLog.id)
            ).where(
                PIIDetectionLog.detected_at >= start_date
            ).group_by(PIIDetectionLog.source_type)
            by_source_result = await self.db.execute(by_source_stmt)
            by_source = {row[0]: row[1] for row in by_source_result}
            
            # Daily trend - simplified for now
            trend = []
            
            return DetectionStatsResponse(
                period=period,
                total_detections=total_detections,
                by_entity_type=by_entity_type,
                by_engine=by_engine,
                by_source=by_source,
                trend=trend
            )
        except Exception as e:
            logger.error(f"Error calculating stats: {e}", exc_info=True)
            return DetectionStatsResponse(
                period=period,
                total_detections=0,
                by_entity_type={},
                by_engine={},
                by_source={},
                trend=[]
            )
