import pika
from config import QueueService, Queue


class QueryQueueConnection:
    credentials = pika.PlainCredentials(QueueService.username, QueueService.password)
    connection_params = pika.ConnectionParameters(
        host=QueueService.host,
        port=QueueService.port,
        credentials=credentials,
        heartbeat=0,
    )
    connection = pika.BlockingConnection(parameters=connection_params)
    channel = connection.channel()
    channel.queue_declare(queue="NIB QUEUE EXCHANGE")
    print(" [x] Sent 'Hello World!'")
