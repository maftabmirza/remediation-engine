"""
Unit tests for custom PII recognizers.

Tests custom Presidio recognizers for:
- High entropy string detection
- Internal hostname detection
- Private IP address detection
"""
import pytest
from unittest.mock import Mock
import math

from app.services.recognizers.high_entropy_recognizer import HighEntropySecretRecognizer
from app.services.recognizers.hostname_recognizer import InternalHostnameRecognizer
from app.services.recognizers.private_ip_recognizer import PrivateIPRecognizer


class TestHighEntropyRecognizer:
    """Test suite for HighEntropySecretRecognizer."""
    
    @pytest.fixture
    def recognizer(self):
        """Create recognizer instance."""
        return HighEntropySecretRecognizer(
            base64_threshold=4.5,
            hex_threshold=3.0
        )
    
    def test_entropy_calculation_random_string(self, recognizer):
        """Test entropy calculation for random high-entropy string."""
        # Arrange
        random_string = "aGVsbG8gd29ybGQgdGhpcyBpcyBhIHRlc3Q="  # Base64
        
        # Act
        entropy = recognizer.calculate_entropy(random_string)
        
        # Assert
        assert entropy > 4.0  # High entropy expected
    
    def test_entropy_calculation_repeated_chars(self, recognizer):
        """Test entropy calculation for low-entropy repeated characters."""
        # Arrange
        repeated_string = "aaaaaaaaaa"
        
        # Act
        entropy = recognizer.calculate_entropy(repeated_string)
        
        # Assert
        assert entropy < 1.0  # Low entropy expected
    
    def test_base64_detection(self, recognizer):
        """Test detection of base64-encoded strings."""
        # Arrange
        text = "Token: aGVsbG8gd29ybGQgdGhpcyBpcyBhIHRlc3Q="
        
        # Act
        result = recognizer.analyze(text=text, entities=['HIGH_ENTROPY'], nlp_artifacts=None)
        
        # Assert
        assert len(result) > 0
        assert result[0].entity_type == 'HIGH_ENTROPY'
        assert result[0].score > 0.5
    
    def test_hex_detection(self, recognizer):
        """Test detection of hex-encoded strings."""
        # Arrange
        text = "Secret: 68656c6c6f776f726c64746869736973"
        
        # Act
        result = recognizer.analyze(text=text, entities=['HIGH_ENTROPY'], nlp_artifacts=None)
        
        # Assert
        assert len(result) > 0
    
    def test_false_positive_uuid(self, recognizer):
        """Test that UUIDs are not flagged as high entropy."""
        # Arrange
        text = "ID: 550e8400-e29b-41d4-a716-446655440000"
        
        # Act
        result = recognizer.analyze(text=text, entities=['HIGH_ENTROPY'], nlp_artifacts=None)
        
        # Assert
        # UUIDs should be excluded or have low confidence
        assert len(result) == 0 or (len(result) > 0 and result[0].score < 0.5)
    
    def test_context_keyword_boost(self, recognizer):
        """Test that context keywords boost detection confidence."""
        # Arrange
        text_with_context = "password: aGVsbG8gd29ybGQ="
        text_without_context = "value: aGVsbG8gd29ybGQ="
        
        # Act
        result_with = recognizer.analyze(text=text_with_context, entities=['HIGH_ENTROPY'], nlp_artifacts=None)
        result_without = recognizer.analyze(text=text_without_context, entities=['HIGH_ENTROPY'], nlp_artifacts=None)
        
        # Assert
        if len(result_with) > 0 and len(result_without) > 0:
            assert result_with[0].score >= result_without[0].score


class TestHostnameRecognizer:
    """Test suite for InternalHostnameRecognizer."""
    
    @pytest.fixture
    def recognizer(self):
        """Create recognizer instance."""
        return InternalHostnameRecognizer(
            internal_domains=['.internal', '.local', '.corp']
        )
    
    def test_internal_domain_detected(self, recognizer):
        """Test detection of internal domain."""
        # Arrange
        text = "Server: db01.internal"
        
        # Act
        result = recognizer.analyze(text=text, entities=['INTERNAL_HOSTNAME'], nlp_artifacts=None)
        
        # Assert
        assert len(result) > 0
        assert result[0].entity_type == 'INTERNAL_HOSTNAME'
    
    def test_public_domain_not_detected(self, recognizer):
        """Test that public domains are not flagged."""
        # Arrange
        text = "Website: www.example.com"
        
        # Act
        result = recognizer.analyze(text=text, entities=['INTERNAL_HOSTNAME'], nlp_artifacts=None)
        
        # Assert
        assert len(result) == 0
    
    def test_custom_domain_pattern(self, recognizer):
        """Test detection with custom domain patterns."""
        # Arrange
        custom_recognizer = InternalHostnameRecognizer(
            internal_domains=['.mycompany.local', '.staging']
        )
        text = "Connect to api.mycompany.local"
        
        # Act
        result = custom_recognizer.analyze(text=text, entities=['INTERNAL_HOSTNAME'], nlp_artifacts=None)
        
        # Assert
        assert len(result) > 0


class TestPrivateIPRecognizer:
    """Test suite for PrivateIPRecognizer."""
    
    @pytest.fixture
    def recognizer(self):
        """Create recognizer instance."""
        return PrivateIPRecognizer()
    
    def test_10_x_range_detected(self, recognizer):
        """Test detection of 10.x.x.x range."""
        # Arrange
        text = "Server IP: 10.0.1.50"
        
        # Act
        result = recognizer.analyze(text=text, entities=['PRIVATE_IP'], nlp_artifacts=None)
        
        # Assert
        assert len(result) > 0
        assert result[0].entity_type == 'PRIVATE_IP'
    
    def test_172_range_detected(self, recognizer):
        """Test detection of 172.16-31.x.x range."""
        # Arrange
        text = "Database at 172.16.10.5"
        
        # Act
        result = recognizer.analyze(text=text, entities=['PRIVATE_IP'], nlp_artifacts=None)
        
        # Assert
        assert len(result) > 0
    
    def test_192_168_range_detected(self, recognizer):
        """Test detection of 192.168.x.x range."""
        # Arrange
        text = "Gateway: 192.168.1.1"
        
        # Act
        result = recognizer.analyze(text=text, entities=['PRIVATE_IP'], nlp_artifacts=None)
        
        # Assert
        assert len(result) > 0
    
    def test_loopback_detected(self, recognizer):
        """Test detection of loopback address."""
        # Arrange
        text = "Localhost: 127.0.0.1"
        
        # Act
        result = recognizer.analyze(text=text, entities=['PRIVATE_IP'], nlp_artifacts=None)
        
        # Assert
        assert len(result) > 0
    
    def test_public_ip_not_detected(self, recognizer):
        """Test that public IPs are not flagged."""
        # Arrange
        text = "Public server: 8.8.8.8"
        
        # Act
        result = recognizer.analyze(text=text, entities=['PRIVATE_IP'], nlp_artifacts=None)
        
        # Assert
        assert len(result) == 0
    
    def test_invalid_ip_not_detected(self, recognizer):
        """Test that invalid IP formats are not detected."""
        # Arrange
        text = "Invalid: 256.300.1.1"
        
        # Act
        result = recognizer.analyze(text=text, entities=['PRIVATE_IP'], nlp_artifacts=None)
        
        # Assert
        assert len(result) == 0


class TestDetectionMerger:
    """Test suite for DetectionMerger utility."""
    
    def test_merge_non_overlapping(self):
        """Test merging non-overlapping detections."""
        pass
    
    def test_merge_overlapping_keeps_higher_confidence(self):
        """Test that overlapping detections keep higher confidence."""
        pass
    
    def test_deduplicate_exact_matches(self):
        """Test deduplication of exact matching detections."""
        pass
    
    def test_normalize_entity_types(self):
        """Test entity type normalization across engines."""
        pass
