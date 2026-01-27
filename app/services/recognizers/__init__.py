"""
Recognizer registry and initialization.
"""
from typing import List

from presidio_analyzer import EntityRecognizer

from .high_entropy_recognizer import HighEntropySecretRecognizer
from .hostname_recognizer import InternalHostnameRecognizer
from .private_ip_recognizer import PrivateIPRecognizer


def get_custom_recognizers(
    base64_threshold: float = 4.5,
    hex_threshold: float = 3.0,
    internal_domains: List[str] = None
) -> List[EntityRecognizer]:
    """
    Get list of custom recognizers.
    
    Args:
        base64_threshold: Entropy threshold for base64 strings
        hex_threshold: Entropy threshold for hex strings
        internal_domains: List of internal domain suffixes
        
    Returns:
        List of EntityRecognizer instances
    """
    recognizers = [
        HighEntropySecretRecognizer(
            base64_threshold=base64_threshold,
            hex_threshold=hex_threshold
        ),
        InternalHostnameRecognizer(internal_domains=internal_domains),
        PrivateIPRecognizer()
    ]
    
    return recognizers


def register_recognizers(analyzer, recognizers: List[EntityRecognizer]) -> None:
    """
    Register custom recognizers with Presidio analyzer.
    
    Args:
        analyzer: Presidio AnalyzerEngine instance
        recognizers: List of custom recognizers to register
    """
    for recognizer in recognizers:
        analyzer.registry.add_recognizer(recognizer)


__all__ = [
    'HighEntropySecretRecognizer',
    'InternalHostnameRecognizer',
    'PrivateIPRecognizer',
    'get_custom_recognizers',
    'register_recognizers'
]
