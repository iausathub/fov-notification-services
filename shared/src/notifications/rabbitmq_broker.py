import json
import logging
import os
from typing import Any

import aio_pika
from aio_pika import Exchange, Message
from aio_pika.abc import AbstractChannel, AbstractConnection

logger = logging.getLogger(__name__)

# Exchange and queue names
NOTIFICATIONS_EXCHANGE = "fov_notifications"


class RabbitMQBroker:
    """RabbitMQ broker for publishing notifications to queues."""

    def __init__(self, connection_url: str | None = None) -> None:
        """Initialize RabbitMQ broker.

        Args:
            connection_url: RabbitMQ connection URL
        """
        self.connection_url = connection_url or os.getenv(
            "RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"
        )
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: Exchange | None = None

    async def connect(self) -> None:
        """Establish connection to RabbitMQ and set up exchange."""
        if self._connection is None or self._connection.is_closed:
            logger.info(f"Connecting to RabbitMQ at {self.connection_url}")
            self._connection = await aio_pika.connect_robust(self.connection_url)
            self._channel = await self._connection.channel()

            # Declare exchange (topic exchange for routing flexibility)
            self._exchange = await self._channel.declare_exchange(
                NOTIFICATIONS_EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True,  # Survive broker restarts
            )

            logger.info("RabbitMQ connection established")

    async def disconnect(self) -> None:
        """Close RabbitMQ connection."""
        if self._channel:
            await self._channel.close()
            self._channel = None

        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            self._connection = None

        self._exchange = None
        logger.info("RabbitMQ connection closed")

    async def publish_message(
        self,
        routing_key: str,
        message_body: dict[str, Any],
    ) -> None:
        """Publish a message to RabbitMQ.
        routing_key: The routing key to use for the message.
            (e.g. "schedule.update.test_observatory")
        message_body: The message body to publish.
            (e.g. {"type": "schedule_update", "observatory": "test_observatory",
            "data": {"schedule_start": "2026-01-01 12:00:00",
            "schedule_end": "2026-01-01 12:00:00"}})

        Raises:
            RuntimeError: If connection cannot be established.
        """
        if self._exchange is None:
            await self.connect()

        if self._exchange is None:
            raise RuntimeError("Failed to establish RabbitMQ connection")

        body = json.dumps(message_body).encode()
        message = Message(
            body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self._exchange.publish(message, routing_key=routing_key)
        logger.info(f"Published message to RabbitMQ with routing key {routing_key}")
