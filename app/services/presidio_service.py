"""
Presidio service wrapper for PII detection.
"""
from typing import Dict, List, Optional
import logging

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from app.services.recognizers import get_custom_recognizers, register_recognizers


logger = logging.getLogger(__name__)


class PresidioService:
    """
    Service wrapper for Microsoft Presidio PII detection.
    """
    
    def __init__(
        self,
        language: str = "en",
        default_threshold: float = 0.7,
        base64_threshold: float = 4.5,
        hex_threshold: float = 3.0,
        internal_domains: Optional[List[str]] = None
    ):
        """
        Initialize Presidio service.
        
        Args:
            language: Language code for analysis
            default_threshold: Default confidence threshold
            base64_threshold: Entropy threshold for base64 strings
            hex_threshold: Entropy threshold for hex strings
            internal_domains: List of internal domain suffixes
        """
        self.language = language
        self.default_threshold = default_threshold
        
        # Initialize Presidio engines
        logger.info("Initializing Presidio AnalyzerEngine...")
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        
        # Register custom recognizers
        logger.info("Registering custom recognizers...")
        custom_recognizers = get_custom_recognizers(
            base64_threshold=base64_threshold,
            hex_threshold=hex_threshold,
            internal_domains=internal_domains
        )
        register_recognizers(self.analyzer, custom_recognizers)
        
        logger.info(f"Presidio service initialized with {len(custom_recognizers)} custom recognizers")
    
    def analyze(
        self,
        text: str,
        entities: Optional[List[str]] = None,
        language: Optional[str] = None,
        threshold: Optional[float] = None
    ) -> List[RecognizerResult]:
        """
        Analyze text for PII entities.
        
        Args:
            text: Text to analyze
            entities: List of entity types to detect (None = all)
            language: Language code (None = use default)
            threshold: Confidence threshold (None = use default)
            
        Returns:
            List of RecognizerResult objects
        """
        if not text:
            return []
        
        lang = language or self.language
        score_threshold = threshold or self.default_threshold
        
        try:
            results = self.analyzer.analyze(
                text=text,
                entities=entities,
                language=lang,
                score_threshold=score_threshold
            )
            
            logger.debug(f"Presidio analysis found {len(results)} entities")
            return results
            
        except Exception as e:
            logger.error(f"Error analyzing text with Presidio: {e}", exc_info=True)
            return []
    
    def anonymize(
        self,
        text: str,
        analyzer_results: List[RecognizerResult],
        redaction_type: str = "mask",
        mask_char: str = "*"
    ) -> str:
        """
        Anonymize/redact text based on analyzer results.
        
        Args:
            text: Original text
            analyzer_results: Results from analyze()
            redaction_type: Type of redaction (mask, replace, hash, redact)
            mask_char: Character to use for masking
            
        Returns:
            Anonymized text
        """
        if not text or not analyzer_results:
            return text
        
        try:
            # Map redaction types to Presidio operators
            operator_map = {
                "mask": "mask",
                "replace": "replace",
                "hash": "hash",
                "redact": "redact",
                "remove": "redact",
                "tag": "replace"
            }
            
            operator = operator_map.get(redaction_type, "mask")
            
            # Configure operators for each entity type
            operators = {}
            for result in analyzer_results:
                if operator == "mask":
                    operators[result.entity_type] = OperatorConfig(
                        "mask",
                        {"masking_char": mask_char, "chars_to_mask": 100, "from_end": False}
                    )
                elif operator == "replace":
                    operators[result.entity_type] = OperatorConfig(
                        "replace",
                        {"new_value": f"[{result.entity_type}]"}
                    )
                elif operator == "hash":
                    operators[result.entity_type] = OperatorConfig("hash", {})
                else:  # redact
                    operators[result.entity_type] = OperatorConfig("redact", {})
            
            # Anonymize text
            result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=analyzer_results,
                operators=operators
            )
            
            return result.text
            
        except Exception as e:
            logger.error(f"Error anonymizing text with Presidio: {e}", exc_info=True)
            return text
    
    def get_supported_entities(self) -> List[Dict[str, any]]:
        """
        Get list of supported entity types.
        
        Returns:
            List of entity information dicts
        """
        try:
            recognizers = self.analyzer.get_recognizers(language=self.language)
            entities = []
            
            for recognizer in recognizers:
                for entity in recognizer.supported_entities:
                    # Determine if it's a built-in recognizer
                    is_custom = entity in ["HIGH_ENTROPY_SECRET", "INTERNAL_HOSTNAME", "PRIVATE_IP"]
                    
                    # Get description based on entity type
                    descriptions = {
                        "EMAIL_ADDRESS": "Email addresses",
                        "PHONE_NUMBER": "Phone numbers",
                        "US_SSN": "US Social Security Numbers",
                        "CREDIT_CARD": "Credit card numbers",
                        "PERSON": "Person names",
                        "LOCATION": "Geographic locations",
                        "DATE_TIME": "Dates and times",
                        "IP_ADDRESS": "IP addresses",
                        "IBAN_CODE": "IBAN codes",
                        "NRP": "National Registry of Persons",
                        "US_DRIVER_LICENSE": "US driver licenses",
                        "US_PASSPORT": "US passport numbers",
                        "HIGH_ENTROPY_SECRET": "High entropy strings (potential secrets)",
                        "INTERNAL_HOSTNAME": "Internal hostnames",
                        "PRIVATE_IP": "Private IP addresses"
                    }
                    
                    entities.append({
                        "name": entity,
                        "description": descriptions.get(entity, entity.replace("_", " ").title()),
                        "built_in": not is_custom
                    })
            
            # Deduplicate by name
            seen = set()
            unique_entities = []
            for entity in entities:
                if entity["name"] not in seen:
                    seen.add(entity["name"])
                    unique_entities.append(entity)
            
            return unique_entities
            
        except Exception as e:
            logger.error(f"Error getting supported entities: {e}", exc_info=True)
            return []
    
    def update_config(
        self,
        default_threshold: Optional[float] = None,
        language: Optional[str] = None
    ):
        """
        Update configuration.
        
        Args:
            default_threshold: New default threshold
            language: New language code
        """
        if default_threshold is not None:
            self.default_threshold = default_threshold
        
        if language is not None:
            self.language = language
