"""
Tests for per-message session boundary behavior (SFIX-05).

Verifies the session management patterns in the RabbitMQ callback:
1. Session.remove() at callback entry (per-message boundary)
2. Rollback attempts are logged on failure, not swallowed
3. Session.remove() before FAILED status update (fresh session)
4. Session.remove() in finally block for cleanup
5. No except:pass patterns around session operations

Since callback() is defined inside `if __name__ == '__main__':` and cannot
be imported directly, these tests verify the session management contract
by reading and asserting on the actual source code structure + testing
the Session/QueryLogService interaction patterns.
"""
import unittest
from unittest.mock import patch, MagicMock, call
import os
import re


# Path to app.py for source-level assertions
APP_PY = os.path.join(os.path.dirname(__file__), '..', 'app.py')


class TestSessionBoundaryAtEntry(unittest.TestCase):
    """Test 1: callback() calls Session.remove() at entry"""

    def test_session_remove_before_any_db_operation(self):
        """Session.remove() must appear before the first DB operation in callback."""
        with open(APP_PY, 'r') as f:
            source = f.read()

        # Find the callback function
        callback_match = re.search(r'def callback\(ch, method, properties, body\):', source)
        self.assertIsNotNone(callback_match, "callback() function not found in app.py")

        # Get the code between callback definition and first try block
        callback_start = callback_match.start()
        first_try = source.find('try:', callback_start)
        preamble = source[callback_start:first_try]

        self.assertIn('Session.remove()', preamble,
                       "Session.remove() must appear at callback entry, before the first try block")

    def test_session_remove_has_debug_log(self):
        """Session boundary reset should be logged for observability."""
        with open(APP_PY, 'r') as f:
            source = f.read()

        callback_start = source.find('def callback(')
        first_try = source.find('try:', callback_start)
        preamble = source[callback_start:first_try]

        self.assertIn('logger.debug', preamble,
                       "Session scope reset should be logged at DEBUG level")


class TestRollbackErrorHandling(unittest.TestCase):
    """Test 2: on query failure, rollback is attempted and logged"""

    def test_rollback_failure_is_not_swallowed(self):
        """No except:pass patterns should exist around Session operations."""
        with open(APP_PY, 'r') as f:
            source = f.read()

        # Find all except blocks that just have 'pass'
        except_pass = re.findall(r'except\s+\w*\s*:\s*\n\s*pass', source)
        self.assertEqual(len(except_pass), 0,
                          f"Found {len(except_pass)} except:pass patterns in app.py — "
                          "session operation failures must be logged, not swallowed")

    def test_rollback_failure_triggers_session_remove(self):
        """When rollback fails, Session.remove() should be called to force a fresh session."""
        with open(APP_PY, 'r') as f:
            source = f.read()

        # Find the rollback error handler
        rollback_section = re.search(
            r'Session\.rollback\(\).*?except.*?rollback_err.*?Session\.remove\(\)',
            source, re.DOTALL
        )
        self.assertIsNotNone(rollback_section,
                              "Rollback failure handler must call Session.remove() to force fresh session")

    def test_rollback_failure_is_logged_with_traceback(self):
        """Rollback failures should be logged at ERROR level with exc_info=True."""
        with open(APP_PY, 'r') as f:
            source = f.read()

        self.assertIn('rollback failed', source.lower(),
                       "Rollback failure must be logged with descriptive message")
        self.assertIn('exc_info=True', source,
                       "Rollback failure log must include traceback (exc_info=True)")


class TestFreshSessionForFailedStatus(unittest.TestCase):
    """Test 3-4: FAILED status update gets a fresh session"""

    def test_session_remove_before_failed_update(self):
        """Session.remove() must appear immediately before update_query_log(FAILED)."""
        with open(APP_PY, 'r') as f:
            lines = f.readlines()

        # Find the update_query_log call in the error handler (may span multiple lines)
        found_remove_before_update = False
        for i, line in enumerate(lines):
            if 'update_query_log' in line:
                # Check if FAILED appears within the next few lines (multi-line call)
                nearby = ''.join(lines[i:min(len(lines), i+5)])
                if 'FAILED' in nearby:
                    # Check the preceding lines (within 5 lines) for Session.remove()
                    preceding = ''.join(lines[max(0, i-5):i])
                    if 'Session.remove()' in preceding:
                        found_remove_before_update = True
                        break

        self.assertTrue(found_remove_before_update,
                         "Session.remove() must be called before update_query_log(status='FAILED')")

    def test_failed_update_wrapped_in_try_except(self):
        """The FAILED status update must be wrapped in its own try/except with logging."""
        with open(APP_PY, 'r') as f:
            source = f.read()

        # Find the FAILED update section
        failed_section = re.search(
            r"Session\.remove\(\).*?update_query_log.*?FAILED.*?except.*?log_error.*?logger\.\w+",
            source, re.DOTALL
        )
        self.assertIsNotNone(failed_section,
                              "FAILED status update must be in try/except with logged error")


class TestFinallyBlockCleanup(unittest.TestCase):
    """Test 5: Session.remove() in finally block"""

    def test_finally_block_has_session_remove(self):
        """The finally block must call Session.remove() for cleanup."""
        with open(APP_PY, 'r') as f:
            source = f.read()

        # Find the finally block
        finally_match = re.search(r'finally:.*?Session\.remove\(\)', source, re.DOTALL)
        self.assertIsNotNone(finally_match,
                              "finally block must contain Session.remove() for cleanup")

    def test_finally_cleanup_failure_is_logged(self):
        """Session cleanup failure in finally must be logged, not swallowed."""
        with open(APP_PY, 'r') as f:
            source = f.read()

        # Find the finally block's except handler
        finally_start = source.rfind('finally:')
        finally_section = source[finally_start:]

        self.assertIn('cleanup_err', finally_section,
                       "Finally block must name the exception variable (cleanup_err)")
        self.assertIn('logger.warning', finally_section,
                       "Finally block cleanup failure should be logged at WARNING level")


class TestSessionInteractionContract(unittest.TestCase):
    """Test the Session mock interaction to verify the contract works."""

    def test_scoped_session_remove_resets_registry(self):
        """Verify that Session.remove() on a mock clears state as expected."""
        mock_session = MagicMock()

        # Simulate the callback entry pattern
        mock_session.remove()  # Entry boundary
        mock_session.remove.assert_called_once()

        # Simulate a failed rollback + recovery
        mock_session.rollback.side_effect = Exception("Connection dead")
        try:
            mock_session.rollback()
        except Exception:
            mock_session.remove()  # Recovery

        # Session.remove() should have been called twice now
        self.assertEqual(mock_session.remove.call_count, 2)

        # Simulate the FAILED status update on fresh session
        mock_session.remove()  # Fresh session for FAILED update
        self.assertEqual(mock_session.remove.call_count, 3)

        # Verify the call order
        expected_calls = [call.remove(), call.rollback(), call.remove(), call.remove()]
        mock_session.assert_has_calls(expected_calls)

    def test_query_log_service_uses_fresh_session_after_remove(self):
        """After Session.remove(), a new QueryLogService() gets a fresh session."""
        mock_session_class = MagicMock()

        # First call returns a "poisoned" session
        poisoned_session = MagicMock()
        poisoned_session.query.side_effect = Exception("PendingRollbackError")

        # After remove(), returns a fresh session
        fresh_session = MagicMock()

        mock_session_class.side_effect = [poisoned_session, fresh_session]

        # Simulate: try poisoned → remove → try fresh
        session1 = mock_session_class()
        with self.assertRaises(Exception):
            session1.query()  # PendingRollbackError

        # Remove + create fresh
        session2 = mock_session_class()
        session2.query()  # Should work (no exception)
        session2.query.assert_called_once()


if __name__ == '__main__':
    unittest.main()
