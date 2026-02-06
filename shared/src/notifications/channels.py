from abc import ABC, abstractmethod
from typing import Any


class NotificationChannel(ABC):
    """Abstract interface for direct user notification channels.

    Channels send notifications directly to end users (e.g. email).
    Event types and payload shape are defined by the calling service
    (operator, observer); the channel only needs to render and deliver.
    """

    @abstractmethod
    async def send(
        self,
        recipient: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Send a notification to an end user.

        Args:
            recipient: End user identifier (e.g. email address).
            event_type: Event type (e.g. "schedule_update", "fov_alert",
                "pass_interference_alert"). Used for subject/template choice.
            payload: Event data. Structure is defined by the service that
                calls this; the channel may use it for body/subject.
        """
        pass
