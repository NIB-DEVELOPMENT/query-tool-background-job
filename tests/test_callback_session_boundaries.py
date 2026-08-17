"""
Per-message session boundary contract for the RabbitMQ callback (v1 / master).

Guards the fix for incident 68444: a single DPY-4011 connection drop poisoned a
worker's shared scoped_session, and because the failure was swallowed the worker
stayed alive-and-healthy while silently killing every subsequent job — nine
reports left PENDING across five users over six days, 2 of 8 workers affected.

`callback()` is defined inside `if __name__ == '__main__':` so it cannot be
imported. These are therefore source-level assertions on app.py, the same
approach used by the staging suite (test_callback_session_management.py).
"""
import os
import re
import unittest

APP_PY = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _source():
    with open(APP_PY, "r", encoding="utf-8") as fh:
        return fh.read()


def _callback_body(source):
    start = source.find("def callback(")
    assert start != -1, "callback() not found in app.py"
    return source[start:]


class TestSessionBoundaryAtEntry(unittest.TestCase):
    def test_session_removed_before_first_try(self):
        """Each message must start on a clean session, whatever the last one did."""
        source = _source()
        start = source.find("def callback(")
        self.assertNotEqual(start, -1, "callback() not found")
        preamble = source[start:source.find("try:", start)]
        self.assertIn(
            "Session.remove()", preamble,
            "Session.remove() must run at callback entry, before the first try")

    def test_entry_reset_is_logged(self):
        source = _source()
        start = source.find("def callback(")
        preamble = source[start:source.find("try:", start)]
        self.assertIn(
            "Session scope reset", preamble,
            "the per-message reset should be observable in the logs")


class TestRollbackFailureIsNotSwallowed(unittest.TestCase):
    def test_no_bare_pass_after_rollback(self):
        """`except Exception: pass` around rollback is what hid the poisoning.

        rollback() on an invalidated connection raises; swallowing that leaves
        the session dead for the life of the process.
        """
        body = _callback_body(_source())
        rollback_at = body.find("Session.rollback()")
        self.assertNotEqual(rollback_at, -1, "Session.rollback() not found")
        window = body[rollback_at:rollback_at + 400]
        self.assertNotRegex(
            window, r"except Exception:\s*\n\s*pass",
            "rollback failure must be reported, never silently passed")

    def test_rollback_failure_falls_back_to_remove(self):
        body = _callback_body(_source())
        rollback_at = body.find("Session.rollback()")
        window = body[rollback_at:rollback_at + 700]
        self.assertIn(
            "Session.remove()", window,
            "if rollback fails the session must be discarded outright")


class TestFailedStatusWriteGetsFreshSession(unittest.TestCase):
    def test_session_removed_before_failed_update(self):
        """The FAILED write is the only signal the user gets — it must not run
        on a session that may still be unusable, or the row stays PENDING."""
        body = _callback_body(_source())
        update_at = body.find("status='FAILED'")
        self.assertNotEqual(update_at, -1, "FAILED status update not found")
        preceding = body[max(0, update_at - 700):update_at]
        self.assertIn(
            "Session.remove()", preceding,
            "Session.remove() must precede the FAILED status update")


class TestFinallyCleanup(unittest.TestCase):
    def test_session_removed_in_finally(self):
        body = _callback_body(_source())
        finally_at = body.find("finally:")
        self.assertNotEqual(finally_at, -1, "finally block not found")
        window = body[finally_at:finally_at + 600]
        self.assertIn(
            "Session.remove()", window,
            "the finally block must release the session before the next message")

    def test_message_still_acknowledged(self):
        """Session cleanup must not cost us the ack, or the message redelivers
        forever — the 156-restart poison loop of 2026-07-13."""
        body = _callback_body(_source())
        finally_at = body.find("finally:")
        window = body[finally_at:finally_at + 900]
        self.assertIn("basic_ack", window, "ack must remain in the finally block")
        self.assertLess(
            window.find("Session.remove()"), window.find("basic_ack"),
            "cleanup runs before the ack, and must be exception-guarded so a "
            "cleanup failure cannot skip it")


class TestSessionIsImported(unittest.TestCase):
    def test_session_imported_from_src(self):
        self.assertRegex(
            _source(), r"from src import .*\bSession\b",
            "Session must be imported for the boundary handling to work")


if __name__ == "__main__":
    unittest.main()
