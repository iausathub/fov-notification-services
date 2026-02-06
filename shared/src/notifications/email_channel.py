import logging
from typing import Any

from notifications.channels import NotificationChannel

logger = logging.getLogger(__name__)


class EmailChannel(NotificationChannel):
    """Email implementation using a single generic send(event_type, payload)."""

    def __init__(self, smtp_server: str | None = None, smtp_port: int = 587) -> None:
        """Initialize email channel.

        Args:
            smtp_server: SMTP server address
            smtp_port: SMTP server port
        """
        # TODO: Implement email configuration
        # self.smtp_server = smtp_server or os.getenv("SMTP_SERVER")
        # self.smtp_port = smtp_port
        logger.info("EmailChannel initialized (not yet implemented)")

    async def send(
        self,
        recipient: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Send a notification via email. Uses event_type for subject/template."""
        # TODO: Implement email sending; use event_type to choose subject/body
        logger.info(
            f"Would send {event_type} email to {recipient}: %s",
            list(payload.keys()),
        )
        raise NotImplementedError("Email sending not yet implemented")
