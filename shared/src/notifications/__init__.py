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
        List of default recipient addresses
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
    """Add a notification channel

    Args:
        channel: The NotificationChannel instance to add.
    """
    global _channels
    _channels.append(channel)


def clear_channels() -> None:
    """Clear all notification channels"""
    global _channels
    _channels = []


async def publish(routing_key: str, payload: dict[str, Any]) -> None:
    """Publish a message to the broker.
    routing_key: The routing key to use for the message.
        (e.g. "schedule.update.test_observatory")
    payload: The payload to publish.
        (e.g. {"type": "schedule_update", "observatory": "test_observatory",
        "data": {"schedule_start": "2026-01-01 12:00:00",
        "schedule_end": "2026-01-01 12:00:00"}})

    Raises:
        Exception: If the message cannot be published.
    """
    try:
        broker = get_broker()
        await broker.publish_message(routing_key, payload)
    except Exception as e:
        logger.error("Failed to publish to broker: %s", e, exc_info=True)


async def send_to_recipients(
    recipients: list[str],
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Send a notification to each recipient via all configured channels.
    recipients: The list of recipients to send the notification to.
    event_type: The event type to send the notification for.
    payload: The payload to send the notification for.

    Raises:
        Exception: If the notification cannot be sent.
    """
    if not recipients:
        return
    channels = get_channels()
    if not channels:
        return
    for channel in channels:
        for recipient in recipients:
            try:
                await channel.send(recipient, event_type, payload)
            except Exception as e:
                logger.error(
                    "Failed to send via %s to %s: %s",
                    type(channel).__name__,
                    recipient,
                    e,
                    exc_info=True,
                )
