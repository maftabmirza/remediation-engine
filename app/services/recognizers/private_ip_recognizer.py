"""
Custom recognizer for private IP addresses (RFC 1918).
"""
import re
from typing import Optional

from presidio_analyzer import Pattern, PatternRecognizer


# Private IP ranges according to RFC 1918
PRIVATE_RANGES = [
    "10.0.0.0/8",      # Class A: 10.0.0.0 - 10.255.255.255
    "172.16.0.0/12",   # Class B: 172.16.0.0 - 172.31.255.255
    "192.168.0.0/16",  # Class C: 192.168.0.0 - 192.168.255.255
    "127.0.0.0/8",     # Loopback: 127.0.0.0 - 127.255.255.255
]


class PrivateIPRecognizer(PatternRecognizer):
    """
    Recognizer for private IP addresses.
    
    Detects IPv4 addresses in private ranges (RFC 1918).
    """
    
    PATTERNS = [
        Pattern(
            name="ipv4_address",
            regex=r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
            score=0.5
        ),
    ]
    
    def __init__(
        self,
        supported_language: str = "en",
        supported_entity: str = "PRIVATE_IP"
    ):
        """
        Initialize the private IP recognizer.
        
        Args:
            supported_language: Language code
            supported_entity: Entity type name
        """
        super().__init__(
            supported_entity=supported_entity,
            patterns=self.PATTERNS,
            context=[],
            supported_language=supported_language
        )
    
    def validate_result(self, pattern_text: str) -> Optional[bool]:
        """
        Validate if the matched IP is in a private range.
        
        Args:
            pattern_text: The matched text
            
        Returns:
            True if it's a private IP, False otherwise
        """
        return self.is_private_ip(pattern_text)
    
    @staticmethod
    def is_private_ip(ip: str) -> bool:
        """
        Check if IP address is in a private range.
        
        Args:
            ip: IP address string
            
        Returns:
            True if it's a private IP
        """
        try:
            # Parse IP address
            octets = [int(x) for x in ip.split('.')]
            
            if len(octets) != 4:
                return False
            
            # Check each octet is valid (0-255)
            if any(o < 0 or o > 255 for o in octets):
                return False
            
            # Check private ranges
            # 10.0.0.0/8
            if octets[0] == 10:
                return True
            
            # 172.16.0.0/12 (172.16.0.0 - 172.31.255.255)
            if octets[0] == 172 and 16 <= octets[1] <= 31:
                return True
            
            # 192.168.0.0/16
            if octets[0] == 192 and octets[1] == 168:
                return True
            
            # 127.0.0.0/8 (Loopback)
            if octets[0] == 127:
                return True
            
            return False
            
        except (ValueError, AttributeError):
            return False
