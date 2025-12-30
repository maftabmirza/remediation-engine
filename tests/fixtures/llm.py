"""
LLM (Large Language Model) provider mocks for pytest tests.

This module provides mocks for LLM API calls to avoid actual API requests during tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional


@pytest.fixture
def mock_claude_response() -> Dict[str, Any]:
    """Mock response from Claude API."""
    return {
        "id": "msg_test123",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": "**Root Cause**: Nginx service crashed due to configuration error.\n\n**Impact**: Web application is unavailable to users.\n\n**Immediate Actions**:\n1. Check Nginx error logs\n2. Verify configuration syntax\n3. Restart Nginx service\n\n**Remediation Steps**:\n1. SSH to web-server-01\n2. Run: sudo nginx -t\n3. Run: sudo systemctl restart nginx\n4. Run: sudo systemctl status nginx"
            }
        ],
        "model": "claude-3-sonnet-20240229",
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 150,
            "output_tokens": 100
        }
    }


@pytest.fixture
def mock_openai_response() -> Dict[str, Any]:
    """Mock response from OpenAI API."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1704067200,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "**Root Cause**: Database connection pool exhausted.\n\n**Impact**: Application cannot process requests.\n\n**Immediate Actions**:\n1. Check active database connections\n2. Identify long-running queries\n3. Restart application server"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 80,
            "total_tokens": 200
        }
    }


@pytest.fixture
def mock_analysis_result() -> Dict[str, Any]:
    """Mock parsed alert analysis result."""
    return {
        "root_cause": "Nginx service crashed due to configuration error",
        "impact": "Web application is unavailable to users",
        "immediate_actions": [
            "Check Nginx error logs",
            "Verify configuration syntax",
            "Restart Nginx service"
        ],
        "remediation_steps": [
            "SSH to web-server-01",
            "Run: sudo nginx -t",
            "Run: sudo systemctl restart nginx",
            "Run: sudo systemctl status nginx"
        ],
        "confidence": "high",
        "severity_assessment": "critical"
    }


@pytest.fixture
def mock_llm_service():
    """Mock LLM service with async methods."""
    mock = MagicMock()
    
    # Mock analyze_alert method
    mock.analyze_alert = AsyncMock(return_value={
        "root_cause": "Test root cause",
        "impact": "Test impact",
        "immediate_actions": ["Action 1", "Action 2"],
        "remediation_steps": ["Step 1", "Step 2"],
        "confidence": "medium"
    })
    
    # Mock send_chat_message method
    mock.send_chat_message = AsyncMock(return_value={
        "response": "This is a test chat response",
        "tokens_used": 50
    })
    
    # Mock generate_runbook method
    mock.generate_runbook = AsyncMock(return_value={
        "name": "Generated Runbook",
        "steps": [
            {"order": 1, "command": "test command 1"},
            {"order": 2, "command": "test command 2"}
        ]
    })
    
    return mock


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic API client."""
    with patch('anthropic.Anthropic') as mock:
        # Create a mock client instance
        client = MagicMock()
        mock.return_value = client
        
        # Mock the messages.create method
        client.messages.create = AsyncMock()
        
        yield client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI API client."""
    with patch('openai.OpenAI') as mock:
        # Create a mock client instance
        client = MagicMock()
        mock.return_value = client
        
        # Mock the chat.completions.create method
        client.chat.completions.create = AsyncMock()
        
        yield client


@pytest.fixture
def mock_llm_rate_limit_error():
    """Mock LLM API rate limit error (429)."""
    class RateLimitError(Exception):
        def __init__(self):
            self.status_code = 429
            self.message = "Rate limit exceeded"
    
    return RateLimitError()


@pytest.fixture
def mock_llm_timeout_error():
    """Mock LLM API timeout error."""
    class TimeoutError(Exception):
        def __init__(self):
            self.message = "Request timeout"
    
    return TimeoutError()


@pytest.fixture
def mock_llm_invalid_api_key_error():
    """Mock LLM API invalid API key error (401)."""
    class AuthenticationError(Exception):
        def __init__(self):
            self.status_code = 401
            self.message = "Invalid API key"
    
    return AuthenticationError()


@pytest.fixture
def mock_embedding_response():
    """Mock embedding vector response."""
    import numpy as np
    
    # Generate a random 1536-dimension vector (OpenAI embedding size)
    return {
        "embedding": np.random.rand(1536).tolist(),
        "model": "text-embedding-ada-002",
        "usage": {
            "prompt_tokens": 10,
            "total_tokens": 10
        }
    }


@pytest.fixture
def mock_llm_provider_config():
    """Mock LLM provider configuration."""
    return {
        "anthropic": {
            "api_key": "test-anthropic-key",
            "model": "claude-3-sonnet-20240229",
            "temperature": 0.3,
            "max_tokens": 2000
        },
        "openai": {
            "api_key": "test-openai-key",
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 2000
        }
    }


@pytest.fixture(autouse=True)
def disable_llm_api_calls(monkeypatch):
    """
    Automatically disable real LLM API calls in all tests.
    
    Set MOCK_LLM_RESPONSES=true to use this fixture.
    Tests that need real API calls can override this fixture.
    """
    import os
    
    if os.getenv("MOCK_LLM_RESPONSES", "true").lower() == "true":
        # Patch Anthropic client
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-mock-key")
        
        # Patch OpenAI client  
        monkeypatch.setenv("OPENAI_API_KEY", "test-mock-key")
