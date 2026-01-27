"""
Detection result merger and deduplicator.
"""
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DetectionMerger:
    """Utility for merging and deduplicating detection results."""
    
    @staticmethod
    def merge(
        presidio_results: List[Dict[str, Any]],
        secret_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge results from both engines.
        
        Args:
            presidio_results: Results from Presidio
            secret_results: Results from detect-secrets
            
        Returns:
            Combined list of detections
        """
        all_results = []
        
        # Add Presidio results
        for result in presidio_results:
            all_results.append({
                'entity_type': result.get('entity_type'),
                'engine': 'presidio',
                'value': result.get('value', ''),
                'start': result.get('start', 0),
                'end': result.get('end', 0),
                'confidence': result.get('confidence', 0.0),
                'context': result.get('context', '')
            })
        
        # Add detect-secrets results
        for result in secret_results:
            all_results.append({
                'entity_type': result.get('secret_type', 'SECRET'),
                'engine': 'detect_secrets',
                'value': result.get('value', ''),
                'start': result.get('start', 0),
                'end': result.get('end', 0),
                'confidence': result.get('confidence', 0.9),
                'context': result.get('context', '')
            })
        
        return all_results
    
    @staticmethod
    def deduplicate(
        results: List[Dict[str, Any]],
        overlap_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate overlapping detections.
        
        When two detections overlap significantly, keep the one with higher confidence.
        
        Args:
            results: List of detection results
            overlap_threshold: Minimum overlap ratio to consider duplicates (0.0-1.0)
            
        Returns:
            Deduplicated list of detections
        """
        if not results:
            return []
        
        # Sort by confidence (descending) to prioritize higher confidence
        sorted_results = sorted(results, key=lambda x: x.get('confidence', 0), reverse=True)
        
        deduplicated = []
        
        for result in sorted_results:
            is_duplicate = False
            
            for existing in deduplicated:
                overlap = DetectionMerger.calculate_overlap(result, existing)
                
                if overlap >= overlap_threshold:
                    is_duplicate = True
                    logger.debug(
                        f"Filtering duplicate: {result['entity_type']} at {result['start']}-{result['end']} "
                        f"(overlap {overlap:.2f} with {existing['entity_type']})"
                    )
                    break
            
            if not is_duplicate:
                deduplicated.append(result)
        
        # Sort by position in text
        return sorted(deduplicated, key=lambda x: x.get('start', 0))
    
    @staticmethod
    def calculate_overlap(r1: Dict[str, Any], r2: Dict[str, Any]) -> float:
        """
        Calculate overlap ratio between two detections.
        
        Args:
            r1: First detection result
            r2: Second detection result
            
        Returns:
            Overlap ratio (0.0 to 1.0)
        """
        start1, end1 = r1.get('start', 0), r1.get('end', 0)
        start2, end2 = r2.get('start', 0), r2.get('end', 0)
        
        # No overlap
        if end1 <= start2 or end2 <= start1:
            return 0.0
        
        # Calculate overlap
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        overlap_length = overlap_end - overlap_start
        
        # Calculate union
        union_start = min(start1, start2)
        union_end = max(end1, end2)
        union_length = union_end - union_start
        
        if union_length == 0:
            return 0.0
        
        return overlap_length / union_length
    
    @staticmethod
    def normalize_entity_type(engine: str, entity_type: str) -> str:
        """
        Normalize entity type names across engines.
        
        Args:
            engine: Detection engine name
            entity_type: Original entity type
            
        Returns:
            Normalized entity type
        """
        # Map common entity types
        normalization_map = {
            'presidio': {
                'EMAIL_ADDRESS': 'EMAIL',
                'PHONE_NUMBER': 'PHONE',
                'US_SSN': 'SSN',
                'CREDIT_CARD': 'CREDIT_CARD',
                'PERSON': 'PERSON_NAME',
            },
            'detect_secrets': {
                'Base64HighEntropyString': 'HIGH_ENTROPY_BASE64',
                'HexHighEntropyString': 'HIGH_ENTROPY_HEX',
                'AWSKeyDetector': 'AWS_KEY',
                'GitHubTokenDetector': 'GITHUB_TOKEN',
                'PrivateKeyDetector': 'PRIVATE_KEY',
                'JwtTokenDetector': 'JWT_TOKEN',
            }
        }
        
        engine_map = normalization_map.get(engine, {})
        return engine_map.get(entity_type, entity_type)
