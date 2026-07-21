import sentry_sdk
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.crons import capture_checkin
from sentry_sdk.crons.consts import MonitorStatus
import logging
import socket
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

MONITOR_SLUG = "bg-job-consumer-heartbeat"
MONITOR_CONFIG = {
    "schedule": {"type": "interval", "value": 5, "unit": "minute"},
    "checkin_margin": 2,
    "max_runtime": 10,
    "failure_issue_threshold": 1,
    "recovery_threshold": 1,
}


def _before_send_handler(event, hint):
    """Drop info-level events — they belong in logs, not Sentry issues."""
    if event.get('level') == 'info':
        logger.debug("Dropped info-level Sentry event: %s", event.get('message', 'N/A'))
        return None
    return event


class SentryService:
    """
    Centralized Sentry service for error tracking and performance monitoring.
    Provides methods to initialize Sentry, add context, and track custom events.
    """

    _initialized = False

    @staticmethod
    def resolve_environment(config_class):
        """Environment contract: the mounted config.py may set SENTRY_ENVIRONMENT
        on the config class (preferred; the v2 stack mounts "production-v2") or
        provide the legacy get_environment(); with neither, default to "production"."""
        environment = getattr(config_class, "SENTRY_ENVIRONMENT", None)
        if environment:
            return environment
        get_environment = getattr(config_class, "get_environment", None)
        if callable(get_environment):
            return get_environment()
        return "production"

    @classmethod
    def initialize(cls, config_class):
        """
        Initialize Sentry with the provided configuration class.

        Args:
            config_class: One of SentryDevConfig, SentryStagingConfig, SentryProductionConfig
        """
        if cls._initialized:
            return

        environment = cls.resolve_environment(config_class)

        # Configure logging integration
        logging_integration = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        )

        # Configure SQLAlchemy integration for query tracking
        sqlalchemy_integration = SqlalchemyIntegration()

        sentry_sdk.init(
            dsn=config_class.dsn,
            environment=environment,
            traces_sample_rate=config_class.traces_sample_rate,
            profiles_sample_rate=config_class.profiles_sample_rate,
            send_default_pii=config_class.send_default_pii,
            enable_tracing=config_class.enable_tracing,
            before_send=_before_send_handler,
            integrations=[
                logging_integration,
                sqlalchemy_integration,
            ],
        )

        cls._initialized = True

        # Tag all events with replica hostname for multi-replica identification
        sentry_sdk.set_tag("replica", socket.gethostname())

        print(f" [*] Sentry initialized for environment: {environment}")

    @classmethod
    def set_user_context(cls, user_id: int, email: Optional[str] = None,
                         department: Optional[str] = None):
        """
        Set user context for all subsequent Sentry events.

        Args:
            user_id: User ID executing the query
            email: User's email address
            department: User's department
        """
        context = {
            "id": str(user_id),
        }
        if email:
            context["email"] = email
        if department:
            context["department"] = department

        sentry_sdk.set_user(context)

    @classmethod
    def set_query_context(cls, query_id: int, query_name: str,
                          query_params: Optional[Dict] = None):
        """
        Set query-specific context as Sentry tags and context.

        Args:
            query_id: ID of the query being executed
            query_name: Name of the query
            query_params: Parameters passed to the query
        """
        sentry_sdk.set_tag("query_id", str(query_id))
        sentry_sdk.set_tag("query_name", query_name)

        # Add detailed query context
        sentry_sdk.set_context("query", {
            "query_id": query_id,
            "query_name": query_name,
            "query_params": query_params or {}
        })

    @classmethod
    def add_breadcrumb(cls, message: str, category: str = "info",
                       level: str = "info", data: Optional[Dict] = None):
        """
        Add a breadcrumb to track the execution flow.

        Args:
            message: Breadcrumb message
            category: Category (e.g., 'rabbitmq', 'database', 'file_io')
            level: Severity level ('debug', 'info', 'warning', 'error')
            data: Additional data dictionary
        """
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {}
        )

    @classmethod
    def capture_message(cls, message: str, level: str = "info",
                        tags: Optional[Dict] = None):
        """
        Capture a custom message event (for successful completions, warnings, etc.).

        Args:
            message: Message to send
            level: Severity level ('debug', 'info', 'warning', 'error', 'fatal')
            tags: Additional tags for this event
        """
        with sentry_sdk.push_scope() as scope:
            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)
            sentry_sdk.capture_message(message, level=level)

    @classmethod
    def capture_exception(cls, exception: Exception, tags: Optional[Dict] = None):
        """
        Explicitly capture an exception.

        Args:
            exception: Exception to capture
            tags: Additional tags for this event
        """
        with sentry_sdk.push_scope() as scope:
            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)
            sentry_sdk.capture_exception(exception)

    @classmethod
    def start_transaction(cls, name: str, op: str = "task"):
        """
        Start a Sentry transaction for performance monitoring.

        Args:
            name: Transaction name (e.g., "process_query_message")
            op: Operation type (e.g., "task", "http", "db.query")

        Returns:
            Transaction object (use as context manager)
        """
        return sentry_sdk.start_transaction(name=name, op=op)

    @classmethod
    def start_span(cls, op: str, description: str):
        """
        Start a span within the current transaction.

        Args:
            op: Operation type (e.g., "db.query", "file.write", "email.send")
            description: Description of the operation

        Returns:
            Span object (use as context manager)
        """
        return sentry_sdk.start_span(op=op, description=description)

    @classmethod
    def send_heartbeat(cls, status=MonitorStatus.OK):
        """
        Send a cron monitor heartbeat to Sentry.

        Called after each processed message and during idle periods to prove
        consumer liveness. If Sentry misses a heartbeat for >10 minutes,
        it fires a P1 "Consumer Down" alert.

        Args:
            status: MonitorStatus.OK for healthy, MonitorStatus.ERROR for failure
        """
        capture_checkin(
            monitor_slug=MONITOR_SLUG,
            status=status,
            monitor_config=MONITOR_CONFIG,
        )

    @classmethod
    def clear_context(cls):
        """Clear user and query context (useful between message processing)."""
        sentry_sdk.set_user(None)
        sentry_sdk.set_context("query", None)
