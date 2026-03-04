"""
Email notification provider.

Sends HTML/plain-text emails via async SMTP using aiosmtplib.
Jinja2 templates are used for the HTML body.
"""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.schemas_notification import NotificationMessage, ProviderResult
from app.services.notification.providers.base import BaseNotificationProvider

logger = logging.getLogger(__name__)


class EmailProvider(BaseNotificationProvider):
    """Delivers notifications via async SMTP (aiosmtplib)."""

    provider_name = "email"

    async def send(
        self,
        channel_config: dict[str, Any],
        message: NotificationMessage,
    ) -> ProviderResult:
        """
        Send an email notification via SMTP.

        Args:
            channel_config: Must contain smtp_host, smtp_port, from_address, to_addresses.
                            Optionally: smtp_user, smtp_password, use_tls (bool).
            message: Rendered notification message.

        Returns:
            ProviderResult indicating success or failure.
        """
        try:
            import aiosmtplib  # noqa: PLC0415 – optional at import time
        except ImportError:
            return ProviderResult(
                success=False,
                error="aiosmtplib is not installed. Add 'aiosmtplib>=2.0,<3.0' to requirements.txt.",
            )

        smtp_host: str | None = channel_config.get("smtp_host")
        smtp_port: int = int(channel_config.get("smtp_port", 587))
        smtp_user: str | None = channel_config.get("smtp_user")
        smtp_password: str | None = channel_config.get("smtp_password")
        from_address: str | None = channel_config.get("from_address")
        to_addresses: list[str] = channel_config.get("to_addresses", [])
        use_tls: bool = bool(channel_config.get("use_tls", True))

        if not smtp_host:
            return ProviderResult(success=False, error="smtp_host is required")
        if not from_address:
            return ProviderResult(success=False, error="from_address is required")
        if not to_addresses:
            return ProviderResult(success=False, error="to_addresses must contain at least one address")

        # Build MIME message
        mime_msg = MIMEMultipart("alternative")
        mime_msg["Subject"] = f"[{(message.severity or 'INFO').upper()}] {message.title}"
        mime_msg["From"] = from_address
        mime_msg["To"] = ", ".join(to_addresses)

        plain_part = MIMEText(message.body, "plain", "utf-8")
        html_part = MIMEText(_build_html_body(message), "html", "utf-8")
        mime_msg.attach(plain_part)
        mime_msg.attach(html_part)

        try:
            await aiosmtplib.send(
                mime_msg,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_password,
                start_tls=use_tls,
            )

            recipient_summary = ", ".join(to_addresses)
            logger.info("Email sent to %s for event %s", recipient_summary, message.event_type)
            return ProviderResult(
                success=True,
                recipient=recipient_summary,
            )

        except Exception as exc:  # noqa: BLE001
            error = f"SMTP error sending email: {exc}"
            logger.warning("Email send failed: %s", error)
            return ProviderResult(success=False, error=error)

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """
        Validate email channel configuration.

        Args:
            config: Channel config dict.

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []
        if not config.get("smtp_host"):
            errors.append("smtp_host is required for email channels")
        if not config.get("from_address"):
            errors.append("from_address is required for email channels")
        to_addresses = config.get("to_addresses", [])
        if not to_addresses:
            errors.append("to_addresses must contain at least one recipient address")
        elif not isinstance(to_addresses, list):
            errors.append("to_addresses must be a list of email strings")
        return errors


# ---------------------------------------------------------------------------
# Simple HTML template
# ---------------------------------------------------------------------------

def _build_html_body(message: NotificationMessage) -> str:
    """
    Build a basic styled HTML email body.

    Args:
        message: Notification message.

    Returns:
        HTML string for the email body.
    """
    severity = (message.severity or "info").lower()
    color_map = {
        "critical": "#dc3545",
        "warning": "#fd7e14",
        "info": "#0d6efd",
        "ok": "#198754",
        "resolved": "#198754",
    }
    accent = color_map.get(severity, "#0d6efd")

    # Build metadata rows
    meta_rows = ""
    meta_fields = [
        ("Severity", message.severity),
        ("Source", message.metadata.get("source")),
        ("Host", message.metadata.get("host")),
        ("Runbook", message.metadata.get("runbook_name")),
    ]
    for label, val in meta_fields:
        if val:
            meta_rows += (
                f"<tr>"
                f"<td style='padding:4px 12px 4px 0;font-weight:600;color:#555;'>{label}</td>"
                f"<td style='padding:4px 0;color:#333;'>{val}</td>"
                f"</tr>"
            )

    alert_url = message.metadata.get("alert_url", "")
    view_btn = ""
    if alert_url:
        view_btn = (
            f"<p style='margin-top:16px;'>"
            f"<a href='{alert_url}' style='background:{accent};color:#fff;"
            f"padding:8px 20px;text-decoration:none;border-radius:4px;font-weight:600;'>View Alert</a>"
            f"</p>"
        )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset='utf-8'></head>
<body style='font-family:Arial,Helvetica,sans-serif;background:#f5f5f5;padding:20px;'>
  <div style='max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;'>
    <div style='background:{accent};padding:16px 24px;'>
      <h2 style='color:#fff;margin:0;font-size:18px;'>{message.title}</h2>
    </div>
    <div style='padding:24px;'>
      <p style='color:#333;line-height:1.6;margin-top:0;'>{message.body}</p>
      {"<table style='border-collapse:collapse;margin-top:16px;'>" + meta_rows + "</table>" if meta_rows else ""}
      {view_btn}
    </div>
    <div style='padding:12px 24px;background:#f8f9fa;border-top:1px solid #dee2e6;'>
      <small style='color:#888;'>AIOps Remediation Engine — automated notification</small>
    </div>
  </div>
</body>
</html>"""
