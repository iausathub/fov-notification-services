"""Notification system using RabbitMQ and/or email."""

import logging
import os
from typing import Any

from notifications.channels import NotificationChannel
from notifications.email_channel import EmailChannel
from notifications.rabbitmq_broker import RabbitMQBroker

logger = logging.getLogger(__name__)

# Global broker instance (for pub/sub messaging)
_broker: RabbitMQBroker | None = None

# Global notification channels (for direct notifications)
_channels: list[NotificationChannel] = []

# Default recipients for direct notifications (from env or config)
_default_recipients: list[str] = []


def get_broker() -> RabbitMQBroker:
    """Get the RabbitMQ broker instance.

    Returns:
        The RabbitMQ broker instance.
    """
    global _broker
    if _broker is None:
        _broker = RabbitMQBroker()

    return _broker


def set_broker(broker: RabbitMQBroker) -> None:
    """Set the broker instance (mainly for testing).

    Args:
        broker: The RabbitMQBroker instance to use.
    """
    global _broker
    _broker = broker


def get_channels() -> list[NotificationChannel]:
    """Get the configured notification channels.

    Returns:
        List of configured NotificationChannel instances.
    """
    global _channels
    if not _channels:
        # Configure channels based on environment variables
        channel_types = os.getenv("NOTIFICATION_CHANNELS", "").lower().split(",")

        for channel_type in channel_types:
            channel_type = channel_type.strip()
            if channel_type == "email":
                _channels.append(EmailChannel())
            elif channel_type:
                logger.warning(f"Unknown notification channel type: {channel_type}")

    return _channels


def get_default_recipients() -> list[str]:
    """Get default recipients for direct notifications.

    Returns:
        List of default recipient addresses (from NOTIFICATION_RECIPIENTS env var).
    """
    global _default_recipients
    if not _default_recipients:
        recipients_str = os.getenv("NOTIFICATION_RECIPIENTS", "")
        if recipients_str:
            _default_recipients = [
                r.strip() for r in recipients_str.split(",") if r.strip()
            ]
    return _default_recipients


def add_channel(channel: NotificationChannel) -> None:
    """Add a notification channel (mainly for testing).

    Args:
        channel: The NotificationChannel instance to add.
    """
    global _channels
    _channels.append(channel)


def clear_channels() -> None:
    """Clear all notification channels (mainly for testing)."""
    global _channels
    _channels = []


# Notification functions - choose broker, channels, or both
async def notify_schedule_update(
    observatory_name: str,
    schedule_data: dict[str, Any],
    recipients: list[str] | None = None,
    use_broker: bool = True,
    use_channels: bool = False,
) -> None:
    """Send a schedule update notification.

    Choose where to send: message broker (RabbitMQ), direct channels (email), or both.

    Args:
        observatory_name: Name of the observatory.
        schedule_data: Schedule data to send.
        recipients: Optional list of recipients for direct notifications.
            If None, uses NOTIFICATION_RECIPIENTS env var if set.
        use_broker: If True, publish to message broker (RabbitMQ).
        use_channels: If True, send via direct notification channels (email, etc.).
    """
    if use_broker:
        try:
            broker = get_broker()
            await broker.publish_schedule_update(observatory_name, schedule_data)
        except Exception as e:
            logger.error(
                f"Failed to publish schedule update to broker: {e}",
                exc_info=True,
            )

    if use_channels:
        recipients = recipients or get_default_recipients()
        if not recipients:
            logger.warning("No recipients specified for schedule update notification")
        else:
            try:
                await _send_via_channels(
                    recipients,
                    "send_schedule_update",
                    observatory_name,
                    schedule_data,
                )
            except Exception as e:
                logger.error(
                    f"Failed to send schedule update via channels: {e}",
                    exc_info=True,
                )


async def notify_fov_alert(
    observatory_name: str,
    observation_id: int,
    alert_data: dict[str, Any],
    recipients: list[str] | None = None,
    use_broker: bool = True,
    use_channels: bool = False,
) -> None:
    """Send an FOV interference alert.

    Choose where to send: message broker (RabbitMQ), direct channels (email), or both.

    Args:
        observatory_name: Name of the observatory.
        observation_id: ID of the observation with interference.
        alert_data: Alert data to send.
        recipients: Optional list of recipients for direct notifications.
            If None, uses NOTIFICATION_RECIPIENTS env var if set.
        use_broker: If True, publish to message broker (RabbitMQ).
        use_channels: If True, send via direct notification channels (email, etc.).
    """
    if use_broker:
        try:
            broker = get_broker()
            await broker.publish_fov_alert(observatory_name, observation_id, alert_data)
        except Exception as e:
            logger.error(
                f"Failed to publish FOV alert to broker: {e}",
                exc_info=True,
            )

    if use_channels:
        recipients = recipients or get_default_recipients()
        if not recipients:
            logger.warning("No recipients specified for FOV alert notification")
        else:
            try:
                await _send_via_channels(
                    recipients,
                    "send_fov_alert",
                    observatory_name,
                    observation_id,
                    alert_data,
                )
            except Exception as e:
                logger.error(
                    f"Failed to send FOV alert via channels: {e}",
                    exc_info=True,
                )


# Helper function for sending via channels
async def _send_via_channels(
    recipients: list[str],
    channel_method: str,
    *args: Any,
) -> None:
    """Helper function to send notifications via all configured channels.

    Args:
        recipients: List of recipients for direct notifications.
        channel_method: Method name to call on each channel
            ('send_schedule_update' or 'send_fov_alert').
        *args: Arguments to pass to the channel method.
    """
    channels = get_channels()
    if not channels:
        return

    for channel in channels:
        method = getattr(channel, channel_method, None)
        if method is None:
            logger.warning(
                f"Channel {type(channel).__name__} does not implement {channel_method}"
            )
            continue

        for recipient in recipients:
            try:
                await method(recipient, *args)
            except Exception as e:
                logger.error(
                    f"Failed to send notification via {type(channel).__name__} "
                    f"to {recipient}: {e}",
                    exc_info=True,
                )
