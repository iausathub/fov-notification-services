"""Notification channels for direct user notifications (email, etc.).

This module provides an abstraction layer for direct notification channels,
separate from message brokers which handle pub/sub messaging between services.

Key difference:
- MessageBroker: Publishes messages to queues/exchanges for OTHER SERVICES to consume
  (service-to-service communication, e.g., RabbitMQ)
- NotificationChannel: Sends notifications directly to END USERS (humans)
  (service-to-human communication, e.g., Email)
"""

from abc import ABC, abstractmethod
from typing import Any


class NotificationChannel(ABC):
    """Abstract interface for direct user notification channels.

    This abstraction allows switching between different notification channels
    (Email, etc.) without changing the rest of the codebase.

    Unlike MessageBroker (which publishes to queues for services to consume),
    these channels send notifications directly to end users (humans).
    For example:
    - EmailChannel sends an email to admin@example.com
    """

    @abstractmethod
    async def send_schedule_update(
        self,
        recipient: str,
        observatory_name: str,
        schedule_data: dict[str, Any],
    ) -> None:
        """Send a schedule update notification directly to an end user.

        This sends the notification directly to the recipient (e.g., via email),
        NOT through a message broker. This is for notifying humans, not services.

        Args:
            recipient: End user identifier (email address, etc.).
            observatory_name: Name of the observatory.
            schedule_data: Schedule data to send.
        """
        pass

    @abstractmethod
    async def send_fov_alert(
        self,
        recipient: str,
        observatory_name: str,
        observation_id: int,
        alert_data: dict[str, Any],
    ) -> None:
        """Send an FOV interference alert directly to an end user.

        This sends the notification directly to the recipient (e.g., via email),
        NOT through a message broker. This is for notifying humans, not services.

        Args:
            recipient: End user identifier (email address, etc.).
            observatory_name: Name of the observatory.
            observation_id: ID of the observation with interference.
            alert_data: Alert data to send.
        """
        pass
