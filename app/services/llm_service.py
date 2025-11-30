"""
LLM Service - LiteLLM integration for multi-provider support
"""
import json
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from litellm import completion
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LLMProvider, Alert
from app.utils.crypto import decrypt_value

settings = get_settings()


def get_api_key_for_provider(provider: LLMProvider) -> Optional[str]:
    """Get API key for a provider."""
    if provider.api_key_encrypted:
        return decrypt_value(provider.api_key_encrypted)
    
    if provider.provider_type == "anthropic":
        return settings.anthropic_api_key
    elif provider.provider_type == "openai":
        return settings.openai_api_key
    elif provider.provider_type == "google":
        return settings.google_api_key
    
    return None


def build_analysis_prompt(alert: Alert) -> str:
    """Build the analysis prompt for the LLM."""
    alert_name = alert.alert_name
    severity = alert.severity or "unknown"
    instance = alert.instance or "unknown"
    job = alert.job or "unknown"
    status = alert.status
    
    annotations = alert.annotations_json or {}
    summary = annotations.get("summary", "No summary provided")
    description = annotations.get("description", "No description provided")
    
    labels = alert.labels_json or {}
    labels_str = "\n".join([f"  - {k}: {v}" for k, v in labels.items()])
    
    prompt = f"""You are an expert Site Reliability Engineer (SRE) and DevOps specialist. Analyze the following alert and provide actionable remediation guidance.

## Alert Details

- **Alert Name:** {alert_name}
- **Severity:** {severity}
- **Status:** {status}
- **Instance:** {instance}
- **Job:** {job}
- **Timestamp:** {alert.timestamp}

### Summary
{summary}

### Description
{description}

### Labels
{labels_str}

## Your Task

Provide a comprehensive analysis including:

1. **Root Cause Analysis**: What is likely causing this alert? Consider common scenarios.

2. **Impact Assessment**: What is the potential impact if this issue is not addressed?

3. **Immediate Actions**: List 3-5 specific commands or steps to diagnose the issue further.

4. **Remediation Steps**: Provide detailed steps to resolve the issue.

5. **Prevention**: How can this issue be prevented in the future?

6. **Urgency Level**: Rate as LOW, MEDIUM, HIGH, or CRITICAL with justification.

7. **Human Intervention Required**: YES or NO - Does this require immediate human attention?

Format your response in clear sections with markdown formatting.
"""
    
    return prompt


def parse_recommendations(analysis: str) -> List[str]:
    """Extract actionable recommendations from the analysis text."""
    recommendations = []
    lines = analysis.split('\n')
    
    in_actions_section = False
    for line in lines:
        line = line.strip()
        
        if any(keyword in line.lower() for keyword in ['immediate action', 'remediation', 'steps to']):
            in_actions_section = True
            continue
        
        if in_actions_section:
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('*') or line.startswith('•')):
                clean_line = line.lstrip('0123456789.-*• ').strip()
                if clean_line and len(clean_line) > 10:
                    recommendations.append(clean_line)
            
            if line.startswith('#') or (line.startswith('**') and ':' in line):
                if len(recommendations) > 0:
                    in_actions_section = False
    
    return recommendations[:5] if recommendations else ["Review the full analysis for detailed recommendations"]


async def analyze_alert(
    db: Session,
    alert: Alert,
    provider: Optional[LLMProvider] = None
) -> Tuple[str, List[str], LLMProvider]:
    """Analyze an alert using the specified or default LLM provider."""
    if not provider:
        provider = db.query(LLMProvider).filter(
            LLMProvider.is_default == True,
            LLMProvider.is_enabled == True
        ).first()
        
        if not provider:
            provider = db.query(LLMProvider).filter(
                LLMProvider.is_enabled == True
            ).first()
    
    if not provider:
        raise ValueError("No LLM provider configured or enabled")
    
    api_key = get_api_key_for_provider(provider)
    # Note: Ollama might not need an API key, so we allow empty key if provider is ollama
    if not api_key and provider.provider_type != "ollama":
        raise ValueError(f"No API key configured for provider: {provider.name}")
    
    prompt = build_analysis_prompt(alert)
    
    config = provider.config_json or {}
    temperature = config.get("temperature", 0.3)
    max_tokens = config.get("max_tokens", 2000)
    
    try:
        # Prepare model name for LiteLLM
        model_name = provider.model_id
        if provider.provider_type == "anthropic" and not model_name.startswith("anthropic/"):
            # LiteLLM usually handles this, but being explicit helps
            pass 
        elif provider.provider_type == "ollama" and not model_name.startswith("ollama/"):
            model_name = f"ollama/{model_name}"
            
        # Prepare kwargs
        kwargs = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if api_key:
            kwargs["api_key"] = api_key
            
        if provider.api_base_url:
            kwargs["api_base"] = provider.api_base_url

        # Call LiteLLM
        response = completion(**kwargs)
        
        analysis = response.choices[0].message.content
        
    except Exception as e:
        raise RuntimeError(f"LLM API call failed: {str(e)}")
    
    recommendations = parse_recommendations(analysis)
    
    return analysis, recommendations, provider


def get_available_providers(db: Session) -> List[LLMProvider]:
    """Get all enabled LLM providers."""
    return db.query(LLMProvider).filter(
        LLMProvider.is_enabled == True
    ).all()


def get_default_provider(db: Session) -> Optional[LLMProvider]:
    """Get the default LLM provider."""
    return db.query(LLMProvider).filter(
        LLMProvider.is_default == True,
        LLMProvider.is_enabled == True
    ).first()

