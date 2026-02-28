"""
Recognizer registry and initialization.

This module is kept for backward compatibility.
All PII detection now uses:
- Presidio (Microsoft) - for standard PII (email, phone, SSN, credit card, etc.)
- detect-secrets (Yelp) - for secrets (API keys, tokens, passwords, etc.)

No custom recognizers are needed.
"""
from typing import List
from presidio_analyzer import EntityRecognizer


def get_custom_recognizers(**kwargs) -> List[EntityRecognizer]:
    """
    Get list of custom recognizers (returns empty list).
    
    Custom recognizers have been removed. All detection is now handled by:
    - Presidio built-in recognizers (PII)
    - detect-secrets library (secrets/credentials)
    
    Returns:
        Empty list (no custom recognizers)
    """
    return []


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
    'get_custom_recognizers',
    'register_recognizers'
]
