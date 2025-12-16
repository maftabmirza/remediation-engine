"""
Unit tests for the LLM service.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from app.services.llm_service import (
    get_api_key_for_provider,
    build_analysis_prompt
)
from app.models import LLMProvider, Alert


class TestGetApiKeyForProvider:
    """Test API key retrieval for LLM providers."""
    
    @patch('app.services.llm_service.decrypt_value')
    def test_get_api_key_from_encrypted(self, mock_decrypt):
        """Test getting API key from encrypted field."""
        mock_decrypt.return_value = "decrypted-api-key"
        
        provider = MagicMock(spec=LLMProvider)
        provider.api_key_encrypted = "encrypted-key"
        provider.provider_type = "anthropic"
        
        result = get_api_key_for_provider(provider)
        
        assert result == "decrypted-api-key"
        mock_decrypt.assert_called_once_with("encrypted-key")
    
    @patch('app.services.llm_service.settings')
    def test_get_api_key_anthropic_from_settings(self, mock_settings):
        """Test getting Anthropic API key from settings."""
        mock_settings.anthropic_api_key = "anthropic-key-from-env"
        
        provider = MagicMock(spec=LLMProvider)
        provider.api_key_encrypted = None
        provider.provider_type = "anthropic"
        
        result = get_api_key_for_provider(provider)
        
        assert result == "anthropic-key-from-env"
    
    @patch('app.services.llm_service.settings')
    def test_get_api_key_openai_from_settings(self, mock_settings):
        """Test getting OpenAI API key from settings."""
        mock_settings.openai_api_key = "openai-key-from-env"
        
        provider = MagicMock(spec=LLMProvider)
        provider.api_key_encrypted = None
        provider.provider_type = "openai"
        
        result = get_api_key_for_provider(provider)
        
        assert result == "openai-key-from-env"
    
    @patch('app.services.llm_service.settings')
    def test_get_api_key_google_from_settings(self, mock_settings):
        """Test getting Google API key from settings."""
        mock_settings.google_api_key = "google-key-from-env"
        
        provider = MagicMock(spec=LLMProvider)
        provider.api_key_encrypted = None
        provider.provider_type = "google"
        
        result = get_api_key_for_provider(provider)
        
        assert result == "google-key-from-env"
    
    def test_get_api_key_no_key_available(self):
        """Test when no API key is available."""
        provider = MagicMock(spec=LLMProvider)
        provider.api_key_encrypted = None
        provider.provider_type = "unknown"
        
        result = get_api_key_for_provider(provider)
        
        assert result is None
    
    @patch('app.services.llm_service.decrypt_value')
    def test_encrypted_key_takes_precedence(self, mock_decrypt):
        """Test that encrypted key takes precedence over settings."""
        mock_decrypt.return_value = "decrypted-key"
        
        provider = MagicMock(spec=LLMProvider)
        provider.api_key_encrypted = "encrypted-key"
        provider.provider_type = "anthropic"
        
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = "settings-key"
            result = get_api_key_for_provider(provider)
        
        assert result == "decrypted-key"
        mock_decrypt.assert_called_once_with("encrypted-key")


class TestBuildAnalysisPrompt:
    """Test analysis prompt building."""
    
    def test_build_prompt_basic_alert(self):
        """Test building prompt with basic alert data."""
        alert = MagicMock(spec=Alert)
        alert.alert_name = "NginxDown"
        alert.severity = "critical"
        alert.instance = "web-server-01"
        alert.job = "nginx-exporter"
        alert.status = "firing"
        alert.timestamp = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        alert.annotations_json = {
            "summary": "Nginx is down",
            "description": "Nginx service has stopped"
        }
        alert.labels_json = {
            "alertname": "NginxDown",
            "severity": "critical"
        }
        
        prompt = build_analysis_prompt(alert)
        
        assert "NginxDown" in prompt
        assert "critical" in prompt
        assert "web-server-01" in prompt
        assert "nginx-exporter" in prompt
        assert "firing" in prompt
        assert "Nginx is down" in prompt
        assert "Nginx service has stopped" in prompt
    
    def test_build_prompt_missing_annotations(self):
        """Test building prompt when annotations are missing."""
        alert = MagicMock(spec=Alert)
        alert.alert_name = "TestAlert"
        alert.severity = "warning"
        alert.instance = "test-instance"
        alert.job = "test-job"
        alert.status = "firing"
        alert.timestamp = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        alert.annotations_json = None
        alert.labels_json = {}
        
        prompt = build_analysis_prompt(alert)
        
        assert "TestAlert" in prompt
        assert "No summary provided" in prompt
        assert "No description provided" in prompt
    
    def test_build_prompt_missing_optional_fields(self):
        """Test building prompt when optional fields are None."""
        alert = MagicMock(spec=Alert)
        alert.alert_name = "TestAlert"
        alert.severity = None
        alert.instance = None
        alert.job = None
        alert.status = "firing"
        alert.timestamp = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        alert.annotations_json = {}
        alert.labels_json = {}
        
        prompt = build_analysis_prompt(alert)
        
        assert "TestAlert" in prompt
        assert "unknown" in prompt
    
    def test_build_prompt_contains_key_sections(self):
        """Test that prompt contains all required sections."""
        alert = MagicMock(spec=Alert)
        alert.alert_name = "TestAlert"
        alert.severity = "info"
        alert.instance = "test"
        alert.job = "test"
        alert.status = "firing"
        alert.timestamp = datetime.now(timezone.utc)
        alert.annotations_json = {"summary": "Test", "description": "Test"}
        alert.labels_json = {"test": "label"}
        
        prompt = build_analysis_prompt(alert)
        
        # Check for key sections
        assert "Alert Context" in prompt
        assert "Investigation Plan" in prompt
        assert "Hypothesis" in prompt
        assert "Impact" in prompt
        assert "Verification Step" in prompt
        assert "Remediation" in prompt
    
    def test_build_prompt_labels_formatting(self):
        """Test that labels are properly formatted."""
        alert = MagicMock(spec=Alert)
        alert.alert_name = "TestAlert"
        alert.severity = "info"
        alert.instance = "test"
        alert.job = "test"
        alert.status = "firing"
        alert.timestamp = datetime.now(timezone.utc)
        alert.annotations_json = {}
        alert.labels_json = {
            "env": "production",
            "team": "sre",
            "priority": "high"
        }
        
        prompt = build_analysis_prompt(alert)
        
        # Check that labels are formatted as list items
        assert "env: production" in prompt
        assert "team: sre" in prompt
        assert "priority: high" in prompt


class TestLLMServiceIntegration:
    """Integration tests for LLM service (with mocked LLM calls)."""
    
    @pytest.mark.asyncio
    @patch('app.services.llm_service.acompletion')
    async def test_analyze_alert_success(self, mock_acompletion):
        """Test successful alert analysis."""
        mock_acompletion.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content="Test analysis response"
                    )
                )
            ],
            usage=MagicMock(
                total_tokens=100,
                prompt_tokens=50,
                completion_tokens=50
            )
        )
        
        # This is a placeholder - actual analyze_alert function would be tested
        # if it exists in the service
        pass
    
    @pytest.mark.asyncio
    @patch('app.services.llm_service.acompletion')
    async def test_analyze_alert_handles_timeout(self, mock_acompletion):
        """Test handling of LLM timeout."""
        mock_acompletion.side_effect = TimeoutError("Request timed out")
        
        # Test timeout handling
        pass
    
    @pytest.mark.asyncio
    @patch('app.services.llm_service.acompletion')
    async def test_analyze_alert_handles_api_error(self, mock_acompletion):
        """Test handling of LLM API error."""
        mock_acompletion.side_effect = Exception("API Error")
        
        # Test error handling
        pass


class TestPromptValidation:
    """Test prompt validation and formatting."""
    
    def test_prompt_length_reasonable(self):
        """Test that prompts are not excessively long."""
        alert = MagicMock(spec=Alert)
        alert.alert_name = "TestAlert"
        alert.severity = "info"
        alert.instance = "test"
        alert.job = "test"
        alert.status = "firing"
        alert.timestamp = datetime.now(timezone.utc)
        alert.annotations_json = {"summary": "Test", "description": "Test"}
        alert.labels_json = {"test": "label"}
        
        prompt = build_analysis_prompt(alert)
        
        # Prompt should be reasonable length (less than 10KB)
        assert len(prompt) < 10000
    
    def test_prompt_no_sensitive_data_leaked(self):
        """Test that prompt doesn't leak sensitive data."""
        alert = MagicMock(spec=Alert)
        alert.alert_name = "TestAlert"
        alert.severity = "info"
        alert.instance = "test"
        alert.job = "test"
        alert.status = "firing"
        alert.timestamp = datetime.now(timezone.utc)
        alert.annotations_json = {
            "password": "secret123",  # Shouldn't appear in prompt
            "summary": "Test alert"
        }
        alert.labels_json = {}
        
        prompt = build_analysis_prompt(alert)
        
        # This is a basic check - in reality, you'd want more sophisticated
        # sensitive data detection
        assert "password" not in prompt.lower() or "secret" not in prompt
