import logging
import time
import pika
from config import QueueService

logger = logging.getLogger(__name__)


class QueryQueueConnection:
    """RabbitMQ connection with automatic reconnection and exponential backoff."""

    def __init__(self):
        self._connection = None
        self._channel = None
        self.connect()

    def connect(self):
        max_retries = 5
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                credentials = pika.PlainCredentials(
                    QueueService.username, QueueService.password
                )
                params = pika.ConnectionParameters(
                    host=QueueService.host,
                    port=QueueService.port,
                    credentials=credentials,
                    heartbeat=600,
                )
                self._connection = pika.BlockingConnection(parameters=params)
                self._channel = self._connection.channel()
                logger.info("RabbitMQ connection established")
                return
            except pika.exceptions.AMQPConnectionError as e:
                logger.warning(
                    "RabbitMQ connection attempt %d/%d failed: %s",
                    attempt + 1, max_retries, str(e)
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

    @property
    def connection(self):
        if self._connection is None or self._connection.is_closed:
            self.connect()
        return self._connection

    @property
    def channel(self):
        if self._channel is None or self._channel.is_closed:
            self.connect()
        return self._channel

    def close(self):
        try:
            if self._connection and not self._connection.is_closed:
                self._connection.close()
        except Exception:
            pass
