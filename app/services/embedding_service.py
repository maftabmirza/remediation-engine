"""
Embedding Service
Generates vector embeddings using the configured embedding LLM provider.

API key resolution:
1. Explicit api_key argument (for backward compat)
2. Enabled provider with usage_type='embedding' in DB (set in Settings → LLM Providers)

NO .env fallback — embeddings must be explicitly configured via the Settings UI.
"""
import os
from typing import List, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings.

    API key resolution order:
    1. Explicit api_key argument (for backward compat)
    2. Enabled provider with usage_type='embedding' in DB

    No .env fallback — if no embedding provider is configured, is_configured()
    returns False and callers will receive a clear error.
    """

    def __init__(self, api_key: Optional[str] = None, db: Optional["Session"] = None):
        self.model = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
        self.dimensions = int(os.getenv('EMBEDDING_DIMENSIONS', '1536'))
        self._explicit_api_key = api_key
        self._db = db
        self._resolved_api_key: Optional[str] = None
        self._provider_name: Optional[str] = None
        self._resolved_model: Optional[str] = None

    @property
    def api_key(self) -> Optional[str]:
        """Lazily resolve API key on first use."""
        if self._resolved_api_key:
            return self._resolved_api_key

        # 1. Explicit key passed at construction
        if self._explicit_api_key:
            self._resolved_api_key = self._explicit_api_key
            return self._resolved_api_key

        # 2. Look up embedding provider from DB (usage_type='embedding')
        if self._db:
            key, name, model = self._resolve_from_db(self._db)
            if key:
                self._resolved_api_key = key
                self._provider_name = name
                if model:
                    self.model = model
                    self.dimensions = self._infer_dimensions(model)
                return self._resolved_api_key

        # No fallback to env — embedding provider must be explicitly configured
        logger.warning(
            "No embedding provider configured. "
            "Go to Settings → LLM Providers → Add Provider → Usage: Embedding"
        )
        return None

    @staticmethod
    def _infer_dimensions(model: str) -> int:
        """Infer embedding dimensions from model name."""
        if 'text-embedding-3-large' in model:
            return 3072
        if 'text-embedding-ada' in model:
            return 1536
        return 1536  # safe default for text-embedding-3-small and others

    @staticmethod
    def _resolve_from_db(db: "Session"):
        """Return (api_key, provider_name, model_id) from the DB embedding provider.

        Prefers the default embedding provider, falls back to any enabled one.
        """
        try:
            from app.models import LLMProvider
            from app.utils.crypto import decrypt_value

            # Prefer default embedding provider
            provider = db.query(LLMProvider).filter(
                LLMProvider.usage_type == 'embedding',
                LLMProvider.is_enabled == True,
                LLMProvider.is_default == True,
            ).first()

            # Fall back to any enabled embedding provider
            if not provider:
                provider = db.query(LLMProvider).filter(
                    LLMProvider.usage_type == 'embedding',
                    LLMProvider.is_enabled == True,
                ).first()

            if not provider:
                return None, None, None

            api_key = None
            if provider.api_key_encrypted:
                api_key = decrypt_value(provider.api_key_encrypted)

            return api_key, (provider.name or provider.provider_type), provider.model_id

        except Exception as e:
            logger.warning(f"Could not resolve embedding provider from DB: {e}")
            return None, None, None

    def get_provider_display(self) -> str:
        """Human-readable model name for the stats card."""
        _ = self.api_key  # trigger lazy resolution
        return self.model or "Not configured"

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            List of floats (1536 dimensions) or None if failed
        """
        if not self.api_key:
            logger.error("Cannot generate embedding - OPENAI_API_KEY not configured")
            return None
        
        if not text or len(text.strip()) == 0:
            logger.warning("Empty text provided for embedding")
            return None
        
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            
            # Clean and truncate text if needed (OpenAI has token limits)
            text = text.strip()
            if len(text) > 8000:  # Approximate token limit
                text = text[:8000]
            
            response = client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            
            # Verify dimensions
            if len(embedding) != self.dimensions:
                logger.warning(
                    f"Embedding dimension mismatch: expected {self.dimensions}, "
                    f"got {len(embedding)}"
                )
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    def generate_embeddings_batch(
        self, 
        texts: List[str],
        batch_size: int = 100
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to generate embeddings for
            batch_size: Number of texts to process per API call
            
        Returns:
            List of embeddings (same order as input texts)
        """
        if not self.api_key:
            logger.error("Cannot generate embeddings - OPENAI_API_KEY not configured")
            return [None] * len(texts)
        
        if not texts:
            return []
        
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            all_embeddings = []
            
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                # Clean texts
                cleaned_batch = [
                    text.strip()[:8000] if text else "" 
                    for text in batch
                ]
                
                try:
                    response = client.embeddings.create(
                        model=self.model,
                        input=cleaned_batch,
                        encoding_format="float"
                    )
                    
                    # Extract embeddings in order
                    batch_embeddings = [
                        data.embedding for data in response.data
                    ]
                    all_embeddings.extend(batch_embeddings)
                    
                except Exception as e:
                    logger.error(f"Batch embedding failed: {e}")
                    # Add None for failed batch
                    all_embeddings.extend([None] * len(batch))
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            return [None] * len(texts)
    
    def get_embedding_model(self) -> str:
        """Get the current embedding model name."""
        return self.model
    
    def get_dimensions(self) -> int:
        """Get embedding dimensions."""
        return self.dimensions
    
    def is_configured(self) -> bool:
        """Check if the service is properly configured."""
        return self.api_key is not None and len(self.api_key) > 0
    
    def generate_for_alert(self, alert) -> Optional[List[float]]:
        """
        Generate embedding optimized for alert similarity search.
        
        Combines alert metadata into a single text representation:
        - Alert name
        - Severity
        - Labels (JSON)
        - Description from annotations
        
        Args:
            alert: Alert model instance
            
        Returns:
            List of floats (embedding vector) or None if failed
        """
        try:
            # Build text representation of alert
            parts = [
                f"Alert: {alert.alert_name}",
                f"Severity: {alert.severity or 'unknown'}",
            ]
            
            # Add labels if present
            if alert.labels_json:
                import json
                labels = alert.labels_json if isinstance(alert.labels_json, dict) else {}
                if labels:
                    labels_str = ', '.join(f"{k}={v}" for k, v in labels.items())
                    parts.append(f"Labels: {labels_str}")
            
            # Add description from annotations
            if alert.annotations_json:
                annotations = alert.annotations_json if isinstance(alert.annotations_json, dict) else {}
                description = annotations.get('description') or annotations.get('summary')
                if description:
                    parts.append(f"Description: {description}")
            
            # Add instance if present
            if alert.instance:
                parts.append(f"Instance: {alert.instance}")
            
            # Combine all parts
            embedding_text = '\n'.join(parts)
            
            # Generate embedding
            embedding = self.generate_embedding(embedding_text)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate alert embedding: {e}")
            return None
