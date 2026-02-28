"""
Secret detection service using detect-secrets library (Yelp).

This service wraps the detect-secrets library for detecting:
- API keys (AWS, GitHub, Slack, Stripe, etc.)
- Passwords in code (via KeywordDetector)
- JWT tokens
- Private keys (RSA, SSH)
- Basic auth credentials in URLs
- And many more...

Note: High entropy detectors (Base64/Hex) are DISABLED by default
to reduce false positives on regular text.
"""
from typing import Dict, List, Optional, Any
import logging

from detect_secrets.core.scan import scan_line
from detect_secrets.settings import transient_settings


logger = logging.getLogger(__name__)


# Optimized plugin configuration - reduces false positives
# High entropy detectors are DISABLED because they trigger on normal words
OPTIMIZED_PLUGINS = [
    {"name": "ArtifactoryDetector"},
    {"name": "AWSKeyDetector"},
    {"name": "AzureStorageKeyDetector"},
    {"name": "BasicAuthDetector"},
    {"name": "CloudantDetector"},
    {"name": "DiscordBotTokenDetector"},
    {"name": "GitHubTokenDetector"},
    {"name": "GitLabTokenDetector"},
    {"name": "IbmCloudIamDetector"},
    {"name": "IbmCosHmacDetector"},
    {"name": "JwtTokenDetector"},
    {"name": "KeywordDetector"},  # Detects password=, secret=, api_key=, token=
    {"name": "MailchimpDetector"},
    {"name": "NpmDetector"},
    {"name": "OpenAIDetector"},
    {"name": "PrivateKeyDetector"},
    {"name": "PypiTokenDetector"},
    {"name": "SendGridDetector"},
    {"name": "SlackDetector"},
    {"name": "SoftlayerDetector"},
    {"name": "SquareOAuthDetector"},
    {"name": "StripeDetector"},
    {"name": "TelegramBotTokenDetector"},
    {"name": "TwilioKeyDetector"},
    # DISABLED - These cause too many false positives on normal text
    # {"name": "Base64HighEntropyString", "limit": 4.5},
    # {"name": "HexHighEntropyString", "limit": 3.0},
]


class SecretDetectionService:
    """
    Service wrapper for detect-secrets library (Yelp).
    
    Uses optimized plugin configuration to detect secrets with low false positives.
    """
    
    def __init__(
        self,
        base64_limit: float = 4.5,
        hex_limit: float = 3.0,
        keyword_exclude: Optional[List[str]] = None,
        enable_entropy_detectors: bool = False
    ):
        """
        Initialize secret detection service.
        
        Args:
            base64_limit: Entropy limit for base64 strings (only used if enable_entropy_detectors=True)
            hex_limit: Entropy limit for hex strings (only used if enable_entropy_detectors=True)
            keyword_exclude: Keywords to exclude from detection
            enable_entropy_detectors: Enable high entropy string detectors (increases false positives)
        """
        self.base64_limit = base64_limit
        self.hex_limit = hex_limit
        self.keyword_exclude = keyword_exclude or []
        self.enable_entropy_detectors = enable_entropy_detectors
        
        # Build plugin configuration
        self.plugins_config = self._build_plugins_config()
        
        logger.info(f"Secret detection service initialized with {len(self.plugins_config)} plugins")
    
    def _build_plugins_config(self) -> List[Dict[str, Any]]:
        """Build the plugins configuration list."""
        plugins = OPTIMIZED_PLUGINS.copy()
        
        # Optionally add high entropy detectors
        if self.enable_entropy_detectors:
            plugins.append({"name": "Base64HighEntropyString", "limit": self.base64_limit})
            plugins.append({"name": "HexHighEntropyString", "limit": self.hex_limit})
            logger.warning("High entropy detectors enabled - expect more false positives")
        
        return plugins
    
    def scan_text(
        self,
        text: str,
        plugins: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scan text for secrets using detect-secrets.
        
        Args:
            text: Text to scan
            plugins: List of plugin names to use (None = all enabled)
            
        Returns:
            List of detection results
        """
        if not text:
            return []
        
        try:
            results = []
            
            # Track cumulative position for multi-line text
            lines = text.split('\n')
            cumulative_pos = 0
            
            # Use transient_settings for thread-safe scanning
            with transient_settings({"plugins_used": self.plugins_config}):
                # Scan each line (detect-secrets is line-based)
                for line_num, line in enumerate(lines, start=1):
                    if not line.strip():
                        cumulative_pos += len(line) + 1  # +1 for newline
                        continue
                    
                    secrets = list(scan_line(line))
                    for secret in secrets:
                        # Skip if in exclude list
                        if self.keyword_exclude and secret.secret_value:
                            if any(kw in str(secret.secret_value).lower() 
                                   for kw in self.keyword_exclude):
                                continue
                        
                        # Calculate actual position in text
                        secret_value = secret.secret_value if secret.secret_value else ''
                        start_pos = 0
                        end_pos = 0
                        
                        if secret_value:
                            # Find position of secret in the line
                            line_pos = line.find(secret_value)
                            if line_pos >= 0:
                                start_pos = cumulative_pos + line_pos
                                end_pos = start_pos + len(secret_value)
                        
                        result = {
                            'secret_type': secret.type,
                            'value': secret_value if secret_value else '[redacted]',
                            'line_number': line_num,
                            'start': start_pos,
                            'end': end_pos,
                            'confidence': 0.9,  # High confidence for pattern-based detection
                            'plugin': secret.type,
                            'context': line[:100] + ('...' if len(line) > 100 else '')
                        }
                        results.append(result)
                    
                    cumulative_pos += len(line) + 1  # +1 for newline
            
            logger.debug(f"detect-secrets found {len(results)} secrets")
            return results
                    
        except Exception as e:
            logger.error(f"Error scanning text with detect-secrets: {e}", exc_info=True)
            return []
    
    def get_available_plugins(self) -> List[Dict[str, Any]]:
        """
        Get list of available detect-secrets plugins.
        
        Returns:
            List of plugin information dicts
        """
        plugins = [
            {
                "name": "KeywordDetector",
                "description": "Detects secrets by context keywords (password=, secret=, api_key=, token=)",
                "enabled": True,
                "configurable": True
            },
            {
                "name": "AWSKeyDetector",
                "description": "AWS access keys and secret keys",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "AzureStorageKeyDetector",
                "description": "Azure storage account keys",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "BasicAuthDetector",
                "description": "Basic auth credentials in URLs (user:pass@host)",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "GitHubTokenDetector",
                "description": "GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_)",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "GitLabTokenDetector",
                "description": "GitLab tokens (glpat-)",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "JwtTokenDetector",
                "description": "JSON Web Tokens (JWT)",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "OpenAIDetector",
                "description": "OpenAI API keys (sk-)",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "PrivateKeyDetector",
                "description": "RSA/SSH/EC private keys (-----BEGIN ... PRIVATE KEY-----)",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "SlackDetector",
                "description": "Slack tokens (xoxb-, xoxp-, xoxa-, xoxs-)",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "StripeDetector",
                "description": "Stripe API keys (sk_live_, sk_test_, rk_live_, rk_test_)",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "TwilioKeyDetector",
                "description": "Twilio API keys",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "DiscordBotTokenDetector",
                "description": "Discord bot tokens",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "TelegramBotTokenDetector",
                "description": "Telegram bot tokens",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "SendGridDetector",
                "description": "SendGrid API keys",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "MailchimpDetector",
                "description": "Mailchimp API keys",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "NpmDetector",
                "description": "NPM tokens",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "PypiTokenDetector",
                "description": "PyPI tokens",
                "enabled": True,
                "configurable": False
            },
            {
                "name": "Base64HighEntropyString",
                "description": "High entropy base64 strings (DISABLED - causes false positives)",
                "enabled": self.enable_entropy_detectors,
                "configurable": True
            },
            {
                "name": "HexHighEntropyString",
                "description": "High entropy hex strings (DISABLED - causes false positives)",
                "enabled": self.enable_entropy_detectors,
                "configurable": True
            },
        ]
        
        return plugins
    
    def update_config(
        self,
        base64_limit: Optional[float] = None,
        hex_limit: Optional[float] = None,
        keyword_exclude: Optional[List[str]] = None,
        enable_entropy_detectors: Optional[bool] = None
    ):
        """
        Update configuration.
        
        Args:
            base64_limit: New base64 entropy limit
            hex_limit: New hex entropy limit
            keyword_exclude: New keyword exclude list
            enable_entropy_detectors: Enable/disable high entropy detectors
        """
        if base64_limit is not None:
            self.base64_limit = base64_limit
        
        if hex_limit is not None:
            self.hex_limit = hex_limit
        
        if keyword_exclude is not None:
            self.keyword_exclude = keyword_exclude
        
        if enable_entropy_detectors is not None:
            self.enable_entropy_detectors = enable_entropy_detectors
        
        # Rebuild plugins configuration
        self.plugins_config = self._build_plugins_config()
        logger.info(f"Secret detection config updated, {len(self.plugins_config)} plugins active")
