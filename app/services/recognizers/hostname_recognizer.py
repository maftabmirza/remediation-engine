"""
Custom recognizer for internal hostnames.
"""
import re
from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer


# Default internal domain suffixes
DEFAULT_INTERNAL_DOMAINS = [".internal", ".local", ".corp", ".lan", ".private"]


class InternalHostnameRecognizer(PatternRecognizer):
    """
    Recognizer for internal hostnames.
    
    Detects hostnames with internal domain suffixes.
    """
    
    def __init__(
        self,
        internal_domains: Optional[List[str]] = None,
        supported_language: str = "en",
        supported_entity: str = "INTERNAL_HOSTNAME"
    ):
        """
        Initialize the hostname recognizer.
        
        Args:
            internal_domains: List of internal domain suffixes
            supported_language: Language code
            supported_entity: Entity type name
        """
        if internal_domains is None:
            internal_domains = DEFAULT_INTERNAL_DOMAINS
        
        self.internal_domains = internal_domains
        
        # Build patterns for each internal domain
        patterns = []
        for domain in internal_domains:
            # Escape dots in domain for regex
            escaped_domain = re.escape(domain)
            # Match hostname.domain pattern
            pattern = Pattern(
                name=f"hostname{domain}",
                regex=rf"\b[a-zA-Z0-9]([a-zA-Z0-9\-]{{0,61}}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{{0,61}}[a-zA-Z0-9])?)*{escaped_domain}\b",
                score=0.7
            )
            patterns.append(pattern)
        
        super().__init__(
            supported_entity=supported_entity,
            patterns=patterns,
            context=[],
            supported_language=supported_language
        )
    
    def validate_result(self, pattern_text: str) -> Optional[bool]:
        """
        Validate if the matched text is a valid hostname.
        
        Args:
            pattern_text: The matched text
            
        Returns:
            True if valid, False otherwise
        """
        # Check if any internal domain suffix is in the text
        for domain in self.internal_domains:
            if pattern_text.lower().endswith(domain.lower()):
                return True
        return False
