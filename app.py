import os
import sys
import json
from src.query_queue.query_queue_connection import QueryQueueConnection
from src.document_save.document_save_service import DocumentSaveService
from src.email.dto.report_delivery_dto import ReportDeliveryDTO
from src.email.dto.recipient_dto import RecipientDTO
from src.email.query_report_delivered import query_report_delivered
from src.admin.query_log.query_log_service import QueryLogService
from config import Queue, AppConfig
import pika
from src.monitoring.sentry_service import SentryService
import logging

logger = logging.getLogger(__name__)

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))
os.environ.update({'ROOT_PATH': ROOT_PATH})
sys.path.append(os.path.join(ROOT_PATH, 'src'))

from src.queries.query_service import QueryService

# Initialize Sentry with environment-specific configuration
sentry_config = AppConfig.get_sentry_config()
SentryService.initialize(sentry_config)

if __name__ == '__main__':
    connection = QueryQueueConnection()
    channel = connection.channel

    def callback(ch, method, properties, body):
        # Start transaction for entire message processing
        with SentryService.start_transaction(
            name="process_query_message",
            op="rabbitmq.consumer"
        ) as transaction:

            SentryService.add_breadcrumb(
                message="Received message from RabbitMQ",
                category="rabbitmq",
                level="info",
                data={"body_size": len(body)}
            )

            logger.info(f" [x] Received {body}")

            query = None
            query_dto = None
            row_count = 0  # Initialize to avoid NameError in exception handler

            try:
                # Parse message
                with SentryService.start_span(
                    op="deserialize",
                    description="Parse RabbitMQ message to dict"
                ):
                    query = json.loads(body)
                    SentryService.add_breadcrumb(
                        message="Message deserialized successfully",
                        category="processing",
                        level="info",
                        data={"query_id": query.get("id")}
                    )

                # Convert to DTO
                with SentryService.start_span(
                    op="dto.conversion",
                    description="Convert to ExecuteQueryDTO"
                ):
                    query_dto = QueryService().to_execute_query_dto(query=query)

                    # Set Sentry context with user and query information
                    SentryService.set_user_context(
                        user_id=query_dto.user_id,
                        email=query_dto.email,
                        department=query_dto.department
                    )

                    SentryService.set_query_context(
                        query_id=query_dto.query_id,
                        query_name=query_dto.name,
                        query_params=query_dto.query_params
                    )

                    SentryService.add_breadcrumb(
                        message="DTO created and context set",
                        category="processing",
                        level="info",
                        data={
                            "query_id": query_dto.query_id,
                            "query_name": query_dto.name,
                            "user_id": query_dto.user_id
                        }
                    )

                # Execute query
                with SentryService.start_span(
                    op="db.query",
                    description=f"Execute query: {query_dto.name}"
                ) as span:
                    results = QueryService().execute_query_from_rabbitmq(query=query_dto)

                    # Add performance metrics
                    row_count = len(results.rows) if results and hasattr(results, 'rows') else 0
                    span.set_data("row_count", row_count)
                    span.set_data("column_count", len(results.column_names) if results else 0)

                    SentryService.add_breadcrumb(
                        message="Query executed successfully",
                        category="database",
                        level="info",
                        data={"row_count": row_count}
                    )

                # Save to CSV
                with SentryService.start_span(
                    op="file.write",
                    description="Save results to CSV"
                ) as span:
                    save_path = DocumentSaveService().save_to_csv(
                        results=results,
                        query=query_dto
                    )
                    span.set_data("file_path", save_path)

                    SentryService.add_breadcrumb(
                        message="Results saved to CSV",
                        category="file_io",
                        level="info",
                        data={"save_path": save_path}
                    )

                # Generate download link
                download_path = DocumentSaveService().get_download_path(save_path=save_path)

                # Send email
                with SentryService.start_span(
                    op="email.send",
                    description="Send report delivery email"
                ):
                    data = ReportDeliveryDTO(
                        first_name=query_dto.first_name,
                        query_name=query_dto.name,
                        link=download_path
                    )
                    email_recipient = RecipientDTO(
                        email_address=query_dto.email,
                        data=data
                    )
                    query_report_confirmation = query_report_delivered()
                    query_report_confirmation.send(recipients=[email_recipient])

                    SentryService.add_breadcrumb(
                        message="Email sent successfully",
                        category="email",
                        level="info",
                        data={"recipient": query_dto.email}
                    )

                # Update query log
                with SentryService.start_span(
                    op="db.update",
                    description="Update query log status"
                ):
                    QueryLogService().update_query_log(
                        log_id=query["query_log_id"],
                        status='SUCCESS'
                    )

                # Publish cleanup message
                with SentryService.start_span(
                    op="rabbitmq.publish",
                    description="Publish cleanup message"
                ):
                    cleanup_message = json.dumps({'save_path': save_path})
                    channel.basic_publish(
                        exchange=Queue.NIB_QUEUE_EXCHANGE,
                        routing_key=Queue.QUERY_REPORT_CLEANUP_QUEUE,
                        body=cleanup_message,
                        properties=pika.BasicProperties(
                            headers={'x-delay': Queue.DELAY_RATE}
                        )
                    )

                    SentryService.add_breadcrumb(
                        message="Cleanup message published",
                        category="rabbitmq",
                        level="info"
                    )

                # Send success event to Sentry
                SentryService.capture_message(
                    message=f"Query '{query_dto.name}' completed successfully",
                    level="info",
                    tags={
                        "query_id": str(query_dto.query_id),
                        "user_id": str(query_dto.user_id),
                        "row_count": str(row_count)
                    }
                )

                transaction.set_status("ok")

            except Exception as e:
                # Set transaction status
                transaction.set_status("internal_error")

                # Log error with full traceback
                logger.error(f"ERROR processing message: {e}", exc_info=True)

                # Add error breadcrumb
                SentryService.add_breadcrumb(
                    message=f"Error occurred: {str(e)}",
                    category="error",
                    level="error",
                    data={"exception_type": type(e).__name__}
                )

                # Capture exception with context
                SentryService.capture_exception(
                    exception=e,
                    tags={
                        "query_id": str(query_dto.query_id) if query_dto else "unknown",
                        "user_id": str(query_dto.user_id) if query_dto else "unknown",
                        "query_name": query_dto.name if query_dto else "unknown",
                        "error_type": type(e).__name__
                    }
                )

                # Update query log to FAILED if we have the log_id
                if query and "query_log_id" in query:
                    try:
                        QueryLogService().update_query_log(
                            log_id=query["query_log_id"],
                            status='FAILED'
                        )
                    except Exception as log_error:
                        print(f"Failed to update query log: {log_error}")
                        SentryService.capture_exception(log_error)

            finally:
                # Always acknowledge the message
                ch.basic_ack(delivery_tag=method.delivery_tag)

                # Clear Sentry context for next message
                SentryService.clear_context()
        
        
    channel.basic_qos(prefetch_count=100)
    channel.exchange_declare(exchange=Queue.NIB_QUEUE_EXCHANGE, exchange_type=Queue.type, durable=True)
    channel.queue_declare(queue=Queue.QUERY_REPORT_QUEUE, durable=True)
    channel.basic_consume(
        queue=Queue.QUERY_REPORT_QUEUE,
        on_message_callback=callback,
    )
    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()