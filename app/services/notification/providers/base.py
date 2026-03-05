"""
Base notification provider interface.

All concrete providers must subclass BaseNotificationProvider and implement
``send()`` and ``validate_config()``.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.schemas_notification import NotificationMessage, ProviderResult


class BaseNotificationProvider(ABC):
    """Abstract base for notification channel providers."""

    # Override in subclass to set a human-readable name for logging
    provider_name: str = "unknown"

    @abstractmethod
    async def send(
        self,
        channel_config: dict[str, Any],
        message: NotificationMessage,
    ) -> ProviderResult:
        """
        Send a notification via this provider.

        Args:
            channel_config: Decrypted config_json from the NotificationChannel row.
            message: Rendered, ready-to-send notification message.

        Returns:
            ProviderResult with success flag, recipient, and optional error detail.
        """

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """
        Validate a channel configuration dict before saving.

        Args:
            config: The config_json dict to validate.

        Returns:
            List of error strings.  Empty list means the config is valid.
        """
