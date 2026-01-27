"""
Custom recognizer for high entropy strings (potential secrets).
"""
import math
import re
from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer


# Context keywords that indicate a potential secret
CONTEXT_KEYWORDS = [
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "auth", "credential", "private_key", "access_key", "bearer", "authorization",
    "key", "pass"
]


class HighEntropySecretRecognizer(PatternRecognizer):
    """
    Recognizer for high-entropy strings that may be secrets.
    
    Detects random-looking strings with high Shannon entropy,
    especially when near context keywords.
    """
    
    PATTERNS = [
        Pattern(
            name="high_entropy_string",
            regex=r"\b[A-Za-z0-9+/=]{20,}\b",  # Base64-like strings
            score=0.3
        ),
        Pattern(
            name="hex_string",
            regex=r"\b[a-fA-F0-9]{32,}\b",  # Hex strings
            score=0.3
        ),
    ]
    
    CONTEXT = [
        "password", "secret", "token", "key", "auth", "credential",
        "api", "bearer", "access"
    ]
    
    def __init__(
        self,
        base64_threshold: float = 4.5,
        hex_threshold: float = 3.0,
        supported_language: str = "en",
        supported_entity: str = "HIGH_ENTROPY_SECRET"
    ):
        """
        Initialize the high entropy recognizer.
        
        Args:
            base64_threshold: Minimum entropy for base64 strings
            hex_threshold: Minimum entropy for hex strings
            supported_language: Language code
            supported_entity: Entity type name
        """
        super().__init__(
            supported_entity=supported_entity,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language=supported_language
        )
        self.base64_threshold = base64_threshold
        self.hex_threshold = hex_threshold
    
    def validate_result(self, pattern_text: str) -> Optional[bool]:
        """
        Validate if the matched text is actually a high entropy string.
        
        Args:
            pattern_text: The matched text
            
        Returns:
            True if valid, False otherwise, None if unsure
        """
        # Filter out UUIDs (they have predictable structure)
        if self._is_uuid(pattern_text):
            return False
        
        # Calculate entropy
        entropy = self.calculate_entropy(pattern_text)
        
        # Check if it's base64
        if self.is_base64(pattern_text):
            return entropy >= self.base64_threshold
        
        # Check if it's hex
        if self.is_hex(pattern_text):
            return entropy >= self.hex_threshold
        
        # For other strings, use a moderate threshold
        return entropy >= 4.0
    
    @staticmethod
    def calculate_entropy(data: str) -> float:
        """
        Calculate Shannon entropy of a string.
        
        Args:
            data: Input string
            
        Returns:
            Shannon entropy value
        """
        if not data:
            return 0.0
        
        # Count character frequencies
        frequencies = {}
        for char in data:
            frequencies[char] = frequencies.get(char, 0) + 1
        
        # Calculate entropy
        entropy = 0.0
        data_len = len(data)
        for count in frequencies.values():
            probability = count / data_len
            entropy -= probability * math.log2(probability)
        
        return entropy
    
    @staticmethod
    def is_base64(s: str) -> bool:
        """
        Check if string looks like base64.
        
        Args:
            s: Input string
            
        Returns:
            True if it looks like base64
        """
        # Base64 uses A-Z, a-z, 0-9, +, /, and = for padding
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        
        # Length should be multiple of 4 for valid base64
        if len(s) % 4 != 0:
            return False
        
        return bool(base64_pattern.match(s))
    
    @staticmethod
    def is_hex(s: str) -> bool:
        """
        Check if string is hexadecimal.
        
        Args:
            s: Input string
            
        Returns:
            True if it's hexadecimal
        """
        hex_pattern = re.compile(r'^[a-fA-F0-9]+$')
        return bool(hex_pattern.match(s))
    
    @staticmethod
    def _is_uuid(s: str) -> bool:
        """
        Check if string is a UUID.
        
        Args:
            s: Input string
            
        Returns:
            True if it's a UUID
        """
        uuid_pattern = re.compile(
            r'^[a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(s))
