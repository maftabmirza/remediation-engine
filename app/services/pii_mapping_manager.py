"""
PII Mapping Manager

Manages consistent PII placeholders across a conversation session.
Ensures the same PII value always gets the same indexed placeholder,
even across multiple messages in a session.
"""
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class PIIPlaceholder:
    """Represents a PII placeholder with its original value."""
    placeholder: str       # e.g., "[EMAIL_ADDRESS_1]"
    original_value: str    # e.g., "john@example.com"
    entity_type: str       # e.g., "EMAIL_ADDRESS"
    index: int            # e.g., 1


class PIIMappingManager:
    """
    Manages consistent PII placeholders across a conversation session.
    
    This class ensures that:
    1. The same PII value always gets the same placeholder (e.g., john@example.com → [EMAIL_ADDRESS_1])
    2. Different PII values of the same type get unique indexes (jane@company.com → [EMAIL_ADDRESS_2])
    3. Mappings persist across the session lifetime
    4. Mappings can be serialized to JSON for database storage
    
    Usage:
        # Load from existing session
        manager = PIIMappingManager(session.pii_mapping_json)
        
        # Get or create placeholder for a PII value
        placeholder = manager.get_or_create_placeholder("EMAIL_ADDRESS", "john@example.com")
        # Returns "[EMAIL_ADDRESS_1]"
        
        # Same value returns same placeholder
        placeholder = manager.get_or_create_placeholder("EMAIL_ADDRESS", "john@example.com")
        # Still returns "[EMAIL_ADDRESS_1]"
        
        # Different value gets new index
        placeholder = manager.get_or_create_placeholder("EMAIL_ADDRESS", "jane@company.com")
        # Returns "[EMAIL_ADDRESS_2]"
        
        # Save back to session
        session.pii_mapping_json = manager.to_dict()
    """
    
    def __init__(self, existing_mapping: Optional[Dict[str, Any]] = None):
        """
        Initialize the mapping manager.
        
        Args:
            existing_mapping: Existing mapping dict from database (session.pii_mapping_json)
        """
        self._mapping: Dict[str, str] = {}           # placeholder → original_value
        self._counters: Dict[str, int] = {}          # entity_type → current count
        self._reverse: Dict[str, str] = {}           # original_value → placeholder
        
        if existing_mapping:
            self._load_from_dict(existing_mapping)
    
    def _load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load mapping state from a dictionary (from database)."""
        self._counters = data.get("_counters", {})
        self._reverse = data.get("_reverse", {})
        
        # Rebuild forward mapping from stored data
        for key, value in data.items():
            if not key.startswith("_"):  # Skip metadata keys
                self._mapping[key] = value
        
        logger.debug(f"Loaded PII mapping: {len(self._mapping)} placeholders, counters={self._counters}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize mapping state to dictionary for database storage.
        
        Returns:
            Dict suitable for storing in JSON column
        """
        result = dict(self._mapping)  # Copy forward mapping
        result["_counters"] = dict(self._counters)
        result["_reverse"] = dict(self._reverse)
        return result
    
    def get_or_create_placeholder(self, entity_type: str, original_value: str) -> str:
        """
        Get existing placeholder for a value, or create a new indexed one.
        
        Args:
            entity_type: Type of PII entity (e.g., "EMAIL_ADDRESS", "PHONE_NUMBER")
            original_value: The actual PII value (e.g., "john@example.com")
            
        Returns:
            Indexed placeholder string (e.g., "[EMAIL_ADDRESS_1]")
        """
        # Normalize the value for consistent lookup
        normalized_value = original_value.strip()
        
        # Check if this exact value already has a placeholder
        if normalized_value in self._reverse:
            existing_placeholder = self._reverse[normalized_value]
            logger.debug(f"Reusing existing placeholder: {normalized_value} → {existing_placeholder}")
            return existing_placeholder
        
        # Create new indexed placeholder
        current_count = self._counters.get(entity_type, 0)
        new_index = current_count + 1
        self._counters[entity_type] = new_index
        
        placeholder = f"[{entity_type}_{new_index}]"
        
        # Store both forward and reverse mappings
        self._mapping[placeholder] = normalized_value
        self._reverse[normalized_value] = placeholder
        
        logger.info(f"Created new PII placeholder: {entity_type} #{new_index} for value (length={len(normalized_value)})")
        
        return placeholder
    
    def get_placeholder(self, original_value: str) -> Optional[str]:
        """
        Get placeholder for a value if it exists.
        
        Args:
            original_value: The PII value to look up
            
        Returns:
            Placeholder string if found, None otherwise
        """
        return self._reverse.get(original_value.strip())
    
    def get_original(self, placeholder: str) -> Optional[str]:
        """
        Get original value for a placeholder (for de-anonymization).
        
        Args:
            placeholder: The placeholder to look up (e.g., "[EMAIL_ADDRESS_1]")
            
        Returns:
            Original value if found, None otherwise
        """
        return self._mapping.get(placeholder)
    
    def get_all_mappings(self) -> Dict[str, str]:
        """
        Get all placeholder → original mappings (for de-anonymization).
        
        Returns:
            Dict of placeholder → original_value
        """
        return dict(self._mapping)
    
    def get_reverse_mappings(self) -> Dict[str, str]:
        """
        Get all original → placeholder mappings.
        
        Returns:
            Dict of original_value → placeholder
        """
        return dict(self._reverse)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the mapping.
        
        Returns:
            Dict with counts by entity type
        """
        return {
            "total_mappings": len(self._mapping),
            "by_entity_type": dict(self._counters)
        }
    
    def redact_text_with_mappings(
        self, 
        text: str, 
        detections: List[Dict[str, Any]]
    ) -> tuple[str, List[PIIPlaceholder]]:
        """
        Redact text using consistent indexed placeholders.
        
        This method processes detections in reverse order (from end to start)
        to preserve character positions during replacement.
        
        Args:
            text: Original text to redact
            detections: List of detection dicts with entity_type, value, start, end
            
        Returns:
            Tuple of (redacted_text, list of PIIPlaceholder objects created)
        """
        if not detections:
            return text, []
        
        # Sort detections by start position (descending) to replace from end first
        sorted_detections = sorted(detections, key=lambda d: d.get("start", 0), reverse=True)
        
        redacted = text
        placeholders_used: List[PIIPlaceholder] = []
        
        for detection in sorted_detections:
            entity_type = detection.get("entity_type", "UNKNOWN")
            original_value = detection.get("value", "")
            start = detection.get("start", 0)
            end = detection.get("end", 0)
            
            if not original_value or start >= end:
                continue
            
            # Get or create consistent placeholder
            placeholder = self.get_or_create_placeholder(entity_type, original_value)
            
            # Replace in text
            redacted = redacted[:start] + placeholder + redacted[end:]
            
            # Track what we used
            placeholders_used.append(PIIPlaceholder(
                placeholder=placeholder,
                original_value=original_value,
                entity_type=entity_type,
                index=self._counters.get(entity_type, 1)
            ))
        
        return redacted, placeholders_used
    
    def deanonymize_text(self, redacted_text: str) -> str:
        """
        Replace all placeholders with original values (for displaying to user).
        
        Args:
            redacted_text: Text with placeholders
            
        Returns:
            Text with original values restored
        """
        result = redacted_text
        for placeholder, original in self._mapping.items():
            result = result.replace(placeholder, original)
        return result
    
    def clear(self) -> None:
        """Clear all mappings (for testing or session reset)."""
        self._mapping.clear()
        self._counters.clear()
        self._reverse.clear()
        logger.info("PII mapping cleared")
    
    def __len__(self) -> int:
        """Return number of unique PII values mapped."""
        return len(self._mapping)
    
    def __repr__(self) -> str:
        return f"PIIMappingManager(mappings={len(self._mapping)}, counters={self._counters})"
