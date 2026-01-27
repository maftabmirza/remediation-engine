"""
LLM Service - LiteLLM integration for multi-provider support
"""
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from litellm import acompletion
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LLMProvider, Alert
from app.utils.crypto import decrypt_value
from app.metrics import LLM_REQUESTS, LLM_DURATION, LLM_TOKENS
from app.services.ollama_service import ollama_completion

logger = logging.getLogger(__name__)
settings = get_settings()

# Module-level PII service instance (will be injected)
_pii_service = None


def set_pii_service(pii_service):
    """Set the PII service instance for LLM output scanning."""
    global _pii_service
    _pii_service = pii_service


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
    
    prompt = f"""You are Antigravity, an expert Site Reliability Engineer (SRE) and AI coding assistant.
Your goal is to investigate this alert and guide the user through a troubleshooting session until the root cause is found and resolved.

## Alert Context
- **Alert:** {alert_name}
- **Severity:** {severity}
- **Component:** {instance} (Job: {job})
- **Status:** {status}
- **Time:** {alert.timestamp}

### Signal
Summary: {summary}
Description: {description}
Labels:
{labels_str}

## Investigation Plan

You must act as a proactive troubleshooter. Do not just describe the problem; tell the user exactly what to do next.

1.  **Hypothesis**: Briefly state the most likely root cause based on the signals.
2.  **Impact**: One sentence on business/infra impact.
3.  **Verification Step**: Provide the single most important terminal command to test your hypothesis.
    - Format this command in a `bash` code block.
    - Explain what to look for in the output.
4.  **Remediation**: If the hypothesis is confirmed, what will be the fix? (Briefly).

Remember: The user is your eyes and hands. Ask them to run commands and show you the output.
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


async def generate_completion(
    db: Session,
    prompt: str,
    provider: Optional[LLMProvider] = None,
    json_mode: bool = False
) -> Tuple[str, LLMProvider]:
    """
    Generate text completion using the specified or default LLM provider.
    """
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
    if not api_key and provider.provider_type not in ["ollama"]:
        raise ValueError(f"No API key configured for provider: {provider.name}")
    
    config = provider.config_json or {}
    temperature = config.get("temperature", 0.3)
    max_tokens = config.get("max_tokens", 2000)
    
    try:
        logger.info(f"Calling LLM provider: {provider.name} (type: {provider.provider_type})")
        start_time = time.time()
        
        analysis = ""
        
        # Handle Ollama separately
        if provider.provider_type == "ollama":
            messages = [{"role": "user", "content": prompt}]
            
            # TODO: Support JSON mode for Ollama if needed (using format='json')
            
            analysis = await ollama_completion(
                provider=provider,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            duration = time.time() - start_time
            model_name = provider.model_id
            
            # Record metrics
            LLM_REQUESTS.labels(
                provider=provider.provider_type,
                model=model_name,
                status="success"
            ).inc()
            LLM_DURATION.labels(
                provider=provider.provider_type,
                model=model_name
            ).observe(duration)
            
        else:
            # Use LiteLLM
            model_name = provider.model_id
            
            kwargs = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # json_mode: only set response_format for providers that support it
            # Anthropic doesn't support response_format parameter
            if json_mode and provider.provider_type not in ["anthropic"]:
                 kwargs["response_format"] = { "type": "json_object" }
            
            if api_key:
                kwargs["api_key"] = api_key
                
            if provider.api_base_url:
                kwargs["api_base"] = provider.api_base_url

            try:
                response = await acompletion(**kwargs)
                duration = time.time() - start_time
                
                # Record success metrics
                LLM_REQUESTS.labels(
                    provider=provider.provider_type,
                    model=model_name,
                    status="success"
                ).inc()
                LLM_DURATION.labels(
                    provider=provider.provider_type,
                    model=model_name
                ).observe(duration)
                
                analysis = response.choices[0].message.content
                
            except Exception as e:
                duration = time.time() - start_time
                LLM_REQUESTS.labels(
                    provider=provider.provider_type,
                    model=model_name,
                    status="error"
                ).inc()
                LLM_DURATION.labels(
                    provider=provider.provider_type,
                    model=model_name
                ).observe(duration)
                raise

        # Scan and redact PII/secrets from LLM response if service is available
        if _pii_service and analysis:
            try:
                # Detect PII/secrets in the response
                detection_response = await _pii_service.detect(
                    text=analysis,
                    source_type="llm_response",
                    source_id=f"{provider.id}_{int(time.time())}"
                )
                
                # Log detections if any found
                if detection_response.detections:
                    logger.info(
                        f"Detected {detection_response.detection_count} PII/secret(s) "
                        f"in LLM response from {provider.name}"
                    )
                    
                    for detection in detection_response.detections:
                        await _pii_service.log_detection(
                            detection=detection.model_dump(),
                            source_type="llm_response",
                            source_id=f"{provider.id}"
                        )
                    
                    # Redact the response
                    redaction_response = await _pii_service.redact(
                        text=analysis,
                        redaction_type="tag"  # Use tags for LLM responses to maintain readability
                    )
                    
                    analysis = redaction_response.redacted_text
                    
            except Exception as e:
                logger.error(f"PII detection failed for LLM response: {e}")
                # Continue even if PII detection fails

        return analysis, provider
        
    except Exception as e:
        raise RuntimeError(f"LLM API call failed: {str(e)}")


async def analyze_alert(
    db: Session,
    alert: Alert,
    provider: Optional[LLMProvider] = None
) -> Tuple[str, List[str], LLMProvider]:
    """Analyze an alert using the specified or default LLM provider."""
    
    prompt = build_analysis_prompt(alert)
    
    analysis, provider_used = await generate_completion(db, prompt, provider)
    
    recommendations = parse_recommendations(analysis)
    
    return analysis, recommendations, provider_used


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

