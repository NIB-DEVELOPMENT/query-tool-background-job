import os
import sys
import json
from src.query_queue.query_queue_connection import QueryQueueConnection
from src.document_save.document_save_service import DocumentSaveService
from src.email.dto.report_delivery_dto import ReportDeliveryDTO
from src.email.dto.recipient_dto import RecipientDTO
from src.email.query_report_delivered import query_report_delivered
from config import Queue

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))
os.environ.update({'ROOT_PATH': ROOT_PATH})
sys.path.append(os.path.join(ROOT_PATH, 'src'))

from src.queries.query_service import QueryService

if __name__ == '__main__':
    QueryQueueConnection().channel.queue_declare(queue=Queue.NIB_QUEUE_EXCHANGE)
    def callback(ch, method, properties, body):
        print(f" [x] Received {body}")
        query = json.loads(body)
        print(query)
        query_dto=QueryService().to_execute_query_dto(query=query)
        results = QueryService().execute_query_from_rabbitmq(query=query_dto)
        save_path = DocumentSaveService().save_to_csv(results=results, query=query_dto)
        data = ReportDeliveryDTO(first_name=query_dto.first_name, query_name=query_dto.name, file_path=save_path)
        email_recipient = RecipientDTO(email_address=query_dto.email, data=data)
        query_report_confirmation = query_report_delivered()
        query_report_confirmation.send(recipients=[email_recipient])
        
        
    QueryQueueConnection().channel.basic_consume(
        queue=Queue.QUERY_REPORT_QUEUE, 
        on_message_callback=callback, 
        auto_ack=True
    )
    print(' [*] Waiting for messages. To exit press CTRL+C')
    QueryQueueConnection().channel.start_consuming()
    # QueryService().delete_expired_pending_applications()