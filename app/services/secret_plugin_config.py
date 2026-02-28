"""
Plugin configuration manager for detect-secrets.
"""
from typing import Dict, List, Any, Optional


DEFAULT_PLUGINS = {
    "Base64HighEntropyString": {"base64_limit": 4.5},
    "HexHighEntropyString": {"hex_limit": 3.0},
    "KeywordDetector": {"keyword_exclude": []},
    "AWSKeyDetector": {},
    "AzureStorageKeyDetector": {},
    "BasicAuthDetector": {},
    "CloudantDetector": {},
    "DiscordBotTokenDetector": {},
    "GitHubTokenDetector": {},
    "JwtTokenDetector": {},
    "MailchimpDetector": {},
    "NpmDetector": {},
    "PrivateKeyDetector": {},
    "SendGridDetector": {},
    "SlackDetector": {},
    "SoftlayerDetector": {},
    "SquareOAuthDetector": {},
    "StripeDetector": {},
    "TwilioKeyDetector": {},
}


class SecretPluginConfig:
    """Manager for detect-secrets plugin configuration."""
    
    @staticmethod
    def get_default_plugins() -> Dict[str, Dict[str, Any]]:
        """
        Get default plugin configuration.
        
        Returns:
            Dict of plugin names to config dicts
        """
        return DEFAULT_PLUGINS.copy()
    
    @staticmethod
    def configure_high_entropy(
        base64_limit: float,
        hex_limit: float
    ) -> Dict[str, Dict[str, Any]]:
        """
        Configure high entropy string detection.
        
        Args:
            base64_limit: Entropy limit for base64 strings
            hex_limit: Entropy limit for hex strings
            
        Returns:
            Plugin configuration dict
        """
        return {
            "Base64HighEntropyString": {"base64_limit": base64_limit},
            "HexHighEntropyString": {"hex_limit": hex_limit}
        }
    
    @staticmethod
    def configure_keyword_detector(
        keywords: Optional[List[str]] = None,
        keyword_exclude: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Configure keyword detector.
        
        Args:
            keywords: Keywords to detect
            keyword_exclude: Keywords to exclude
            
        Returns:
            Plugin configuration dict
        """
        config = {}
        
        if keywords:
            config["keywords"] = keywords
        
        if keyword_exclude:
            config["keyword_exclude"] = keyword_exclude
        
        return {"KeywordDetector": config}
    
    @staticmethod
    def get_plugin_info() -> List[Dict[str, Any]]:
        """
        Get information about all available plugins.
        
        Returns:
            List of plugin info dicts
        """
        return [
            {
                "name": "Base64HighEntropyString",
                "description": "Detects high entropy base64 strings",
                "configurable": True,
                "default_config": {"base64_limit": 4.5}
            },
            {
                "name": "HexHighEntropyString",
                "description": "Detects high entropy hex strings",
                "configurable": True,
                "default_config": {"hex_limit": 3.0}
            },
            {
                "name": "KeywordDetector",
                "description": "Detects secrets by context keywords",
                "configurable": True,
                "default_config": {"keyword_exclude": []}
            },
            {
                "name": "AWSKeyDetector",
                "description": "AWS access keys (AKIA...)",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "AzureStorageKeyDetector",
                "description": "Azure storage account keys",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "BasicAuthDetector",
                "description": "Basic authentication in URLs",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "CloudantDetector",
                "description": "IBM Cloudant credentials",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "DiscordBotTokenDetector",
                "description": "Discord bot tokens",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "GitHubTokenDetector",
                "description": "GitHub personal access tokens",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "JwtTokenDetector",
                "description": "JSON Web Tokens (JWT)",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "MailchimpDetector",
                "description": "Mailchimp API keys",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "NpmDetector",
                "description": "NPM authentication tokens",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "PrivateKeyDetector",
                "description": "RSA/SSH private keys",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "SendGridDetector",
                "description": "SendGrid API keys",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "SlackDetector",
                "description": "Slack tokens and webhooks",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "SoftlayerDetector",
                "description": "IBM Softlayer credentials",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "SquareOAuthDetector",
                "description": "Square OAuth secrets",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "StripeDetector",
                "description": "Stripe API keys",
                "configurable": False,
                "default_config": {}
            },
            {
                "name": "TwilioKeyDetector",
                "description": "Twilio API keys and tokens",
                "configurable": False,
                "default_config": {}
            }
        ]
    
    @staticmethod
    def merge_configs(
        default_config: Dict[str, Dict[str, Any]],
        custom_config: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Merge custom configuration with defaults.
        
        Args:
            default_config: Default configuration
            custom_config: Custom configuration to overlay
            
        Returns:
            Merged configuration
        """
        merged = default_config.copy()
        
        for plugin_name, plugin_config in custom_config.items():
            if plugin_name in merged:
                merged[plugin_name].update(plugin_config)
            else:
                merged[plugin_name] = plugin_config
        
        return merged
