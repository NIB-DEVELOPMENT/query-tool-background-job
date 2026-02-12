import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.monitoring.sentry_service import SentryService
from config import SentryDevConfig


class TestSentryIntegration(unittest.TestCase):
    """Test cases for Sentry integration"""

    @patch('src.monitoring.sentry_service.sentry_sdk')
    def test_sentry_initialization(self, mock_sentry):
        """Test that Sentry initializes with correct configuration"""
        SentryService._initialized = False  # Reset

        SentryService.initialize(SentryDevConfig)

        # Verify init was called
        mock_sentry.init.assert_called_once()

        # Check arguments
        call_args = mock_sentry.init.call_args
        self.assertEqual(call_args.kwargs['environment'], 'development')
        self.assertEqual(call_args.kwargs['send_default_pii'], True)

    @patch('src.monitoring.sentry_service.sentry_sdk')
    def test_set_user_context(self, mock_sentry):
        """Test setting user context"""
        SentryService.set_user_context(
            user_id=31688,
            email="test@example.com",
            department="HR"
        )

        mock_sentry.set_user.assert_called_once_with({
            "id": "31688",
            "email": "test@example.com",
            "department": "HR"
        })

    @patch('src.monitoring.sentry_service.sentry_sdk')
    def test_set_query_context(self, mock_sentry):
        """Test setting query context"""
        SentryService.set_query_context(
            query_id=123,
            query_name="Test Query",
            query_params={"dept": "HR"}
        )

        mock_sentry.set_tag.assert_any_call("query_id", "123")
        mock_sentry.set_tag.assert_any_call("query_name", "Test Query")

    @patch('src.monitoring.sentry_service.sentry_sdk')
    def test_add_breadcrumb(self, mock_sentry):
        """Test adding breadcrumbs"""
        SentryService.add_breadcrumb(
            message="Test breadcrumb",
            category="test",
            level="info",
            data={"key": "value"}
        )

        mock_sentry.add_breadcrumb.assert_called_once()

    @patch('src.monitoring.sentry_service.sentry_sdk')
    def test_transaction_creation(self, mock_sentry):
        """Test transaction creation"""
        mock_transaction = MagicMock()
        mock_sentry.start_transaction.return_value = mock_transaction

        transaction = SentryService.start_transaction(
            name="test_transaction",
            op="task"
        )

        mock_sentry.start_transaction.assert_called_once_with(
            name="test_transaction",
            op="task"
        )

    @patch('src.monitoring.sentry_service.sentry_sdk')
    def test_capture_exception(self, mock_sentry):
        """Test exception capture with tags"""
        test_exception = ValueError("Test error")

        # Create a mock scope context manager
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__.return_value = mock_scope

        SentryService.capture_exception(
            exception=test_exception,
            tags={"test_tag": "test_value"}
        )

        # Verify tags were set
        mock_scope.set_tag.assert_called_once_with("test_tag", "test_value")

        # Verify capture_exception was called
        mock_sentry.capture_exception.assert_called_once_with(test_exception)

    @patch('src.monitoring.sentry_service.sentry_sdk')
    def test_clear_context(self, mock_sentry):
        """Test clearing context"""
        SentryService.clear_context()

        mock_sentry.set_user.assert_called_once_with(None)
        mock_sentry.set_context.assert_called_once_with("query", None)


if __name__ == '__main__':
    unittest.main()
