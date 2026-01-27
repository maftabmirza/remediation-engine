"""
Secret detection service using detect-secrets library.
"""
from typing import Dict, List, Optional, Any
import logging
import tempfile
import os

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings


logger = logging.getLogger(__name__)


class SecretDetectionService:
    """
    Service wrapper for detect-secrets library.
    """
    
    def __init__(
        self,
        base64_limit: float = 4.5,
        hex_limit: float = 3.0,
        keyword_exclude: Optional[List[str]] = None
    ):
        """
        Initialize secret detection service.
        
        Args:
            base64_limit: Entropy limit for base64 strings
            hex_limit: Entropy limit for hex strings
            keyword_exclude: Keywords to exclude from detection
        """
        self.base64_limit = base64_limit
        self.hex_limit = hex_limit
        self.keyword_exclude = keyword_exclude or []
        
        # Initialize settings
        self.settings = default_settings
        self.settings.filters = {}
        
        # Configure plugins
        self._configure_plugins()
        
        logger.info("Secret detection service initialized")
    
    def _configure_plugins(self):
        """Configure detect-secrets plugins."""
        # Set entropy limits
        self.settings.plugins['Base64HighEntropyString'] = {
            'base64_limit': self.base64_limit
        }
        self.settings.plugins['HexHighEntropyString'] = {
            'hex_limit': self.hex_limit
        }
        
        # Configure keyword detector
        if self.keyword_exclude:
            self.settings.plugins['KeywordDetector'] = {
                'keyword_exclude': ','.join(self.keyword_exclude)
            }
    
    def scan_text(
        self,
        text: str,
        plugins: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scan text for secrets.
        
        Args:
            text: Text to scan
            plugins: List of plugin names to use (None = all enabled)
            
        Returns:
            List of detection results
        """
        if not text:
            return []
        
        try:
            # Create temporary file to scan (detect-secrets works with files)
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write(text)
                temp_path = f.name
            
            try:
                # Create secrets collection and scan
                secrets = SecretsCollection()
                
                # Scan the temporary file
                from detect_secrets.core import scan
                secrets = scan.scan_file(temp_path)
                
                # Convert results to our format
                results = []
                for secret in secrets:
                    result = {
                        'secret_type': secret.type,
                        'line_number': secret.line_number,
                        'start': 0,  # detect-secrets doesn't provide exact position
                        'end': 0,
                        'confidence': 0.9,  # Most detect-secrets plugins have high confidence
                        'plugin': secret.type
                    }
                    results.append(result)
                
                logger.debug(f"detect-secrets found {len(results)} secrets")
                return results
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            logger.error(f"Error scanning text with detect-secrets: {e}", exc_info=True)
            return []
    
    def get_available_plugins(self) -> List[Dict[str, Any]]:
        """
        Get list of available plugins.
        
        Returns:
            List of plugin information dicts
        """
        plugins = [
            {
                "name": "Base64HighEntropyString",
                "description": "Detects high entropy base64 strings",
                "configurable": True
            },
            {
                "name": "HexHighEntropyString",
                "description": "Detects high entropy hex strings",
                "configurable": True
            },
            {
                "name": "KeywordDetector",
                "description": "Detects secrets by context keywords",
                "configurable": True
            },
            {
                "name": "AWSKeyDetector",
                "description": "AWS access keys",
                "configurable": False
            },
            {
                "name": "AzureStorageKeyDetector",
                "description": "Azure storage keys",
                "configurable": False
            },
            {
                "name": "BasicAuthDetector",
                "description": "Basic auth in URLs",
                "configurable": False
            },
            {
                "name": "CloudantDetector",
                "description": "IBM Cloudant credentials",
                "configurable": False
            },
            {
                "name": "DiscordBotTokenDetector",
                "description": "Discord bot tokens",
                "configurable": False
            },
            {
                "name": "GitHubTokenDetector",
                "description": "GitHub tokens (ghp_, gho_, etc.)",
                "configurable": False
            },
            {
                "name": "JwtTokenDetector",
                "description": "JWT tokens",
                "configurable": False
            },
            {
                "name": "MailchimpDetector",
                "description": "Mailchimp API keys",
                "configurable": False
            },
            {
                "name": "NpmDetector",
                "description": "NPM tokens",
                "configurable": False
            },
            {
                "name": "PrivateKeyDetector",
                "description": "RSA/SSH private keys",
                "configurable": False
            },
            {
                "name": "SendGridDetector",
                "description": "SendGrid API keys",
                "configurable": False
            },
            {
                "name": "SlackDetector",
                "description": "Slack tokens",
                "configurable": False
            },
            {
                "name": "SoftlayerDetector",
                "description": "Softlayer credentials",
                "configurable": False
            },
            {
                "name": "SquareOAuthDetector",
                "description": "Square OAuth tokens",
                "configurable": False
            },
            {
                "name": "StripeDetector",
                "description": "Stripe API keys",
                "configurable": False
            },
            {
                "name": "TwilioKeyDetector",
                "description": "Twilio API keys",
                "configurable": False
            }
        ]
        
        return plugins
    
    def update_config(
        self,
        base64_limit: Optional[float] = None,
        hex_limit: Optional[float] = None,
        keyword_exclude: Optional[List[str]] = None
    ):
        """
        Update configuration.
        
        Args:
            base64_limit: New base64 entropy limit
            hex_limit: New hex entropy limit
            keyword_exclude: New keyword exclude list
        """
        if base64_limit is not None:
            self.base64_limit = base64_limit
        
        if hex_limit is not None:
            self.hex_limit = hex_limit
        
        if keyword_exclude is not None:
            self.keyword_exclude = keyword_exclude
        
        # Reconfigure plugins
        self._configure_plugins()
