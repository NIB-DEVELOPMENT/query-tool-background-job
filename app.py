import os
import sys
import json
import signal
from src.query_queue.query_queue_connection import QueryQueueConnection
from src.document_save.document_save_service import DocumentSaveService
from src.document_save.excel_export_service import ExcelExportService
from src.document_save.pdf_export_service import PdfExportService
from src.email.dto.report_delivery_dto import ReportDeliveryDTO
from src.email.dto.recipient_dto import RecipientDTO
from src.email.query_report_delivered import query_report_delivered
from src.admin.query_log.query_log_service import QueryLogService
from config import Queue, AppConfig
from config import OracleDB

# The worker connects as a DBA account, not as the schema owner, so raw SQL
# against query-tool tables MUST be schema-qualified -- the ORM models already
# are (see __table_args__ schema=OracleDB().userName). Unqualified
# `scheduled_report_table` raised ORA-00942 on every scheduled run, so the
# self-reschedule never happened and each schedule fired exactly once
# (2026-08-20, both v2 workers).
SCHEDULED_REPORT_TABLE = f"{OracleDB().userName}.scheduled_report_table"
import pika
from src.monitoring.sentry_service import SentryService
import logging

logger = logging.getLogger(__name__)

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))
os.environ.update({'ROOT_PATH': ROOT_PATH})
sys.path.append(os.path.join(ROOT_PATH, 'src'))

from src.queries.query_service import QueryService
from src import Session

# Initialize Sentry with environment-specific configuration
sentry_config = AppConfig.get_sentry_config()
SentryService.initialize(sentry_config)

if __name__ == '__main__':
    connection = QueryQueueConnection()
    channel = connection.channel

    def graceful_shutdown(signum, frame):
        logger.info("Received signal %s, shutting down gracefully...", signum)
        connection.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

    def callback(ch, method, properties, body):
        # Per-message session boundary — ensure each message starts with a clean session
        Session.remove()
        logger.debug("Session scope reset for message %s", method.delivery_tag)

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

                # A scheduled message is a delayed copy of the schedule as it was
                # when published. If the schedule has since been disabled, or
                # edited/re-armed (next_run_at no longer matches the fire time
                # baked into this message), this copy is stale: ack and skip, or
                # an edit would run the report twice and a disable not at all.
                if query and query.get("scheduled") and query.get("schedule_id"):
                    from sqlalchemy import text as _text
                    _row = Session.execute(
                        _text(f"SELECT is_active, next_run_at FROM {SCHEDULED_REPORT_TABLE} WHERE id = :id"),
                        {"id": query["schedule_id"]},
                    ).fetchone()
                    _expected = query.get("scheduled_for")
                    _actual = _row[1].strftime("%Y-%m-%d %H:%M") if _row and _row[1] else None
                    # scheduled_for is mandatory: a message without it predates the
                    # contract and cannot be matched to the row, so it is stale.
                    if _row is None or not _row[0] or not _expected or _expected != _actual:
                        logger.warning(
                            "Skipping stale scheduled message: schedule_id=%s active=%s scheduled_for=%s next_run_at=%s",
                            query["schedule_id"], _row[0] if _row else None, _expected, _actual,
                        )
                        transaction.set_status("ok")
                        return  # finally block acks

                # Scheduled runs are published in advance with no pre-created
                # log (only the backend's async path pre-creates one), so create
                # it here at run time and inject the id so the downstream guarded
                # updates (EXECUTING/SAVING/COMPLETE) all work unchanged. Wrapped
                # so a log-write failure never blocks report generation.
                if query is not None and "query_log_id" not in query:
                    try:
                        _created_log = QueryLogService().create_run_time_query_log(
                            query=QueryService().get_query_by_id(query_id=query_dto.query_id),
                            nib_user_id=query_dto.user_id,
                        )
                        query["query_log_id"] = _created_log.id
                        logger.info(
                            "Created run-time query log %s for scheduled query %s",
                            _created_log.id, query_dto.query_id,
                        )
                    except Exception as log_create_err:
                        logger.warning("Could not create run-time query log: %s", log_create_err)
                        # A failed flush leaves the session unusable until rolled
                        # back; without this the report itself then died with
                        # "transaction has been rolled back due to a previous
                        # exception during flush" (2026-09-07).
                        try:
                            Session.rollback()
                        except Exception as rb_err:  # noqa: BLE001
                            logger.error("Rollback after failed run-time log failed: %s", rb_err)
                            Session.remove()

                # DS-07 redelivery guard: a redelivered message whose log row
                # already reached a terminal state was finished (or failed) by
                # a previous worker — ack (via finally) and skip, so restart
                # races can never double-process or loop.
                if method.redelivered and query and "query_log_id" in query:
                    try:
                        prior_status = QueryLogService().get_status(log_id=query["query_log_id"])
                    except Exception as guard_err:
                        # Guard is a backstop — on lookup failure, process normally.
                        logger.warning("Redelivery guard status lookup failed: %s", guard_err)
                        prior_status = None
                    if prior_status in ("FAILED", "COMPLETE"):
                        SentryService.add_breadcrumb(
                            message="Redelivered message skipped — log row already terminal",
                            category="rabbitmq",
                            level="warning",
                            data={
                                "query_log_id": query["query_log_id"],
                                "prior_status": prior_status,
                            },
                        )
                        logger.warning(
                            "Skipping redelivered message: query_log_id=%s already %s",
                            query["query_log_id"], prior_status,
                        )
                        transaction.set_status("ok")
                        return  # finally block acks

                # Update status: EXECUTING
                if query and "query_log_id" in query:
                    try:
                        QueryLogService().update_status(log_id=query["query_log_id"], status="EXECUTING")
                    except Exception as status_err:
                        logger.warning("Failed to update status to EXECUTING: %s", status_err)

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

                # Update status: SAVING (with row count)
                if query and "query_log_id" in query:
                    try:
                        QueryLogService().update_status(
                            log_id=query["query_log_id"], status="SAVING", row_count=row_count
                        )
                    except Exception as status_err:
                        logger.warning("Failed to update status to SAVING: %s", status_err)

                # Save results in requested format (csv, xlsx, pdf)
                export_format = query.get("export_format", "csv") if query else "csv"
                with SentryService.start_span(
                    op="file.write",
                    description=f"Save results to {export_format}"
                ) as span:
                    if export_format == "xlsx":
                        save_path = ExcelExportService().save_to_xlsx(
                            results=results, query=query_dto
                        )
                    elif export_format == "pdf":
                        save_path = PdfExportService().save_to_pdf(
                            results=results, query=query_dto
                        )
                    else:
                        save_path = DocumentSaveService().save_to_csv(
                            results=results, query=query_dto
                        )
                    span.set_data("file_path", save_path)
                    span.set_data("export_format", export_format)

                    SentryService.add_breadcrumb(
                        message=f"Results saved to {export_format}",
                        category="file_io",
                        level="info",
                        data={"save_path": save_path, "format": export_format}
                    )

                # Generate download link
                download_path = DocumentSaveService().get_download_path(save_path=save_path)

                # Send email (skip if notify_email is false)
                notify_email = query.get("notify_email", True) if query else True
                if notify_email:
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
                else:
                    logger.info("Email notification skipped (notify_email=false)")

                # Update query log
                with SentryService.start_span(
                    op="db.update",
                    description="Update query log status"
                ):
                    if query and "query_log_id" in query:
                        QueryLogService().update_status(
                            log_id=query["query_log_id"],
                            status='COMPLETE',
                            row_count=row_count,
                            file_path=save_path.lstrip('/'),
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

                # Self-reschedule if this was a scheduled report
                if query and query.get("scheduled") and query.get("schedule_id"):
                    try:
                        from datetime import timedelta
                        from src.clock import now_local

                        schedule_id = query["schedule_id"]
                        # Check last_run_at to prevent duplicate re-publishing
                        from sqlalchemy import text
                        result = Session.execute(
                            text(f"SELECT last_run_at, frequency, day_of_week, day_of_month, run_time, is_active FROM {SCHEDULED_REPORT_TABLE} WHERE id = :id"),
                            {"id": schedule_id}
                        ).fetchone()

                        if result and result[5]:  # is_active
                            now = now_local()
                            frequency = result[1]
                            run_time = result[4] or "08:00"
                            hour, minute = map(int, run_time.split(":"))

                            # Calculate next run
                            if frequency == "daily":
                                next_run = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0)
                            elif frequency == "weekly":
                                next_run = (now + timedelta(days=7)).replace(hour=hour, minute=minute, second=0)
                            elif frequency == "monthly":
                                if now.month == 12:
                                    next_run = now.replace(year=now.year + 1, month=1, day=min(result[3] or 1, 28), hour=hour, minute=minute, second=0)
                                else:
                                    next_run = now.replace(month=now.month + 1, day=min(result[3] or 1, 28), hour=hour, minute=minute, second=0)
                            else:
                                next_run = now + timedelta(days=1)

                            delay_ms = max(int((next_run - now).total_seconds() * 1000), 1000)

                            # Update DB
                            Session.execute(
                                text(f"UPDATE {SCHEDULED_REPORT_TABLE} SET last_run_at = :now, next_run_at = :next WHERE id = :id"),
                                {"now": now, "next": next_run, "id": schedule_id}
                            )
                            Session.commit()

                            # Re-publish with delay. Strip the run-time-injected
                            # query_log_id so the NEXT occurrence creates its own
                            # fresh log instead of mutating this run's log row.
                            republish_body = {k: v for k, v in query.items() if k != "query_log_id"}
                            republish_body["scheduled_for"] = next_run.strftime("%Y-%m-%d %H:%M")
                            channel.basic_publish(
                                exchange=Queue.NIB_QUEUE_EXCHANGE,
                                routing_key=Queue.QUERY_REPORT_QUEUE,
                                body=json.dumps(republish_body),
                                properties=pika.BasicProperties(
                                    delivery_mode=pika.DeliveryMode.Persistent,
                                    headers={"x-delay": delay_ms},
                                ),
                            )
                            logger.info("Rescheduled report: schedule_id=%d, next=%s, delay=%dms",
                                        schedule_id, next_run, delay_ms)
                    except Exception as sched_err:
                        logger.error("Failed to reschedule report: %s", sched_err)

                # Log query completion (breadcrumb-only — no Sentry event)
                logger.info(
                    "Query '%s' completed successfully",
                    query_dto.name,
                    extra={
                        "query_id": query_dto.query_id,
                        "user_id": query_dto.user_id,
                        "row_count": row_count,
                    }
                )

                transaction.set_status("ok")

            except Exception as e:
                # Rollback the DB session to clear any poisoned transaction state.
                try:
                    Session.rollback()
                except Exception as rollback_err:
                    logger.error(
                        "Session rollback failed for query %s, forcing session removal: %s",
                        query_dto.query_id if query_dto else "unknown",
                        rollback_err, exc_info=True
                    )
                    try:
                        Session.remove()
                    except Exception as remove_err:
                        logger.error("Session.remove() also failed: %s", remove_err, exc_info=True)

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
                        Session.remove()  # Force fresh session for status update
                        QueryLogService().update_query_log(
                            log_id=query["query_log_id"],
                            status='FAILED'
                        )
                    except Exception as log_error:
                        logger.error(
                            "Failed to update query log %s to FAILED status: %s",
                            query.get("query_log_id"), log_error, exc_info=True
                        )
                        SentryService.capture_exception(log_error)

            finally:
                # Always acknowledge the message
                ch.basic_ack(delivery_tag=method.delivery_tag)

                # Clean up scoped session — return connection to pool.
                # Without this, a single DB error poisons the session permanently.
                try:
                    Session.remove()
                except Exception as cleanup_err:
                    logger.warning("Session cleanup failed in finally block: %s", cleanup_err)

                # Heartbeat after every processed message (success or failure)
                SentryService.send_heartbeat()

                # Clear Sentry context for next message
                SentryService.clear_context()
        
        
    channel.basic_qos(prefetch_count=5)
    channel.exchange_declare(exchange=Queue.NIB_QUEUE_EXCHANGE, exchange_type=Queue.type, durable=True)
    channel.queue_declare(queue=Queue.QUERY_REPORT_QUEUE, durable=True)
    channel.basic_consume(
        queue=Queue.QUERY_REPORT_QUEUE,
        on_message_callback=callback,
    )
    print(' [*] Waiting for messages. To exit press CTRL+C')

    # Idle heartbeat loop: process_data_events blocks for up to 300s (5 min),
    # then returns so we can send a heartbeat proving the consumer is alive.
    # Replaces channel.start_consuming() which blocks forever with no
    # opportunity to signal liveness during idle periods.
    while True:
        connection.connection.process_data_events(time_limit=300)
        SentryService.send_heartbeat()