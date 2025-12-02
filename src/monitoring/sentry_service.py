import sentry_sdk
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import logging
from typing import Optional, Dict, Any


class SentryService:
    """
    Centralized Sentry service for error tracking and performance monitoring.
    Provides methods to initialize Sentry, add context, and track custom events.
    """

    _initialized = False

    @classmethod
    def initialize(cls, config_class):
        """
        Initialize Sentry with the provided configuration class.

        Args:
            config_class: One of SentryDevConfig, SentryStagingConfig, SentryProductionConfig
        """
        if cls._initialized:
            return

        # Configure logging integration
        logging_integration = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        )

        # Configure SQLAlchemy integration for query tracking
        sqlalchemy_integration = SqlalchemyIntegration()

        sentry_sdk.init(
            dsn=config_class.dsn,
            environment=config_class.get_environment(),
            traces_sample_rate=config_class.traces_sample_rate,
            profiles_sample_rate=config_class.profiles_sample_rate,
            send_default_pii=config_class.send_default_pii,
            enable_tracing=config_class.enable_tracing,
            integrations=[
                logging_integration,
                sqlalchemy_integration,
            ],
        )

        cls._initialized = True
        print(f" [*] Sentry initialized for environment: {config_class.get_environment()}")

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
    def clear_context(cls):
        """Clear user and query context (useful between message processing)."""
        sentry_sdk.set_user(None)
        sentry_sdk.set_context("query", None)
