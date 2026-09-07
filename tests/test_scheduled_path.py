"""
Regression tests for the two defects that killed scheduled reports in
production (2026-08-20, both v2 workers):

1. NIBUserRepo used Flask-SQLAlchemy's `Model.query`, which does not exist on
   this repo's plain declarative models -> `type object 'NIBUser' has no
   attribute 'query'` -> run-time query_log creation failed for every
   scheduled run (no status row, no tracker entry, no download).
2. The self-reschedule SQL referenced `scheduled_report_table` unqualified. The
   worker connects as a DBA account, not the schema owner, so Oracle raised
   ORA-00942 -> no re-publish -> every schedule fired exactly once and died.

Test 1 is a real unit test (mocked session). Test 2 is source-level, like the
session-boundary tests, because callback() is nested under __main__ and cannot
be imported; scripts/verify_scheduled_path.py is the RUNTIME gate for it.
"""
import os
import re
import unittest
from unittest.mock import MagicMock

APP_PY = os.path.join(os.path.dirname(__file__), "..", "app.py")


class TestNIBUserRepoQueriesThroughSession(unittest.TestCase):
    def _repo_with_mock_db(self):
        from src.nib_user.nib_user_repo import NIBUserRepo
        repo = NIBUserRepo()
        repo.db = MagicMock(name="Session")
        return repo

    def test_find_by_id_uses_session_query_not_model_query(self):
        repo = self._repo_with_mock_db()
        from src.nib_user.nib_user_model import NIBUser

        repo._find_by_id(nib_user_id=48539)

        repo.db.query.assert_called_once_with(NIBUser)
        repo.db.query.return_value.filter.return_value.first.assert_called_once()

    def test_find_by_user_id_uses_session_query_not_model_query(self):
        repo = self._repo_with_mock_db()
        from src.nib_user.nib_user_model import NIBUser

        repo._find_by_user_id(user_id="janineo")

        repo.db.query.assert_called_once_with(NIBUser)

    def test_model_has_no_flask_style_query_attribute(self):
        """Documents WHY the fix is needed: the attribute the old code used is absent."""
        from src.nib_user.nib_user_model import NIBUser

        self.assertFalse(hasattr(NIBUser, "query"))


class TestRescheduleSqlIsSchemaQualified(unittest.TestCase):
    def setUp(self):
        with open(APP_PY, "r", encoding="utf-8") as f:
            self.source = f.read()

    def test_no_unqualified_scheduled_report_table_reference(self):
        # Any FROM/UPDATE directly followed by the bare table name is the bug.
        bare = re.findall(r"(?:FROM|UPDATE)\s+scheduled_report_table\b", self.source)
        self.assertEqual(bare, [], f"unqualified references found: {bare}")

    def test_qualified_constant_is_derived_from_config_schema(self):
        self.assertIn(
            'SCHEDULED_REPORT_TABLE = f"{OracleDB().userName}.scheduled_report_table"',
            self.source,
        )
        self.assertEqual(self.source.count("{SCHEDULED_REPORT_TABLE}"), 2,
                         "both the SELECT and the UPDATE must use the constant")

    def test_reschedule_failure_is_logged_not_swallowed(self):
        self.assertIn('logger.error("Failed to reschedule report: %s", sched_err)', self.source)


if __name__ == "__main__":
    unittest.main()


class TestRowCapCoercion(unittest.TestCase):
    """row_cap comes off the queue message and is interpolated into SQL (ROWNUM
    cannot always be bound), so it must be a validated positive int or nothing."""

    def setUp(self):
        from src.queries.query_service import QueryService
        self.coerce = QueryService._coerce_row_cap

    def test_accepts_positive_ints_and_numeric_strings(self):
        self.assertEqual(self.coerce(5000), 5000)
        self.assertEqual(self.coerce("250"), 250)

    def test_rejects_sql_fragments_and_garbage(self):
        self.assertIsNone(self.coerce("1 OR 1=1"))
        self.assertIsNone(self.coerce("5000; DROP TABLE x"))
        self.assertIsNone(self.coerce("abc"))
        self.assertIsNone(self.coerce(object()))

    def test_rejects_non_positive_none_and_bool(self):
        self.assertIsNone(self.coerce(None))
        self.assertIsNone(self.coerce(0))
        self.assertIsNone(self.coerce(-1))
        self.assertIsNone(self.coerce(True))


class TestRunTimeQueryLogResolvesUserByPrimaryKey(unittest.TestCase):
    """Queue messages carry user_id = nib_users.id (PK). The run-time log must
    resolve by that column, not by the auth-service user_id column."""

    def _service(self):
        from src.admin.query_log.query_log_service import QueryLogService
        svc = QueryLogService.__new__(QueryLogService)
        svc.query_log_repo = MagicMock(name="QueryLogRepo")
        svc.nib_user_repo = MagicMock(name="NIBUserRepo")
        return svc

    def test_looks_up_by_id_not_user_id(self):
        svc = self._service()
        svc.create_run_time_query_log(query=MagicMock(name="QueryDTO"), nib_user_id=31688)
        svc.nib_user_repo.find_by_id.assert_called_once_with(nib_user_id=31688)
        svc.nib_user_repo.find_by_user_id.assert_not_called()
        svc.query_log_repo.add_benefit_log.assert_called_once()

    def test_unknown_user_raises_instead_of_none_dot_id(self):
        svc = self._service()
        svc.nib_user_repo.find_by_id.return_value = None
        with self.assertRaises(LookupError):
            svc.create_run_time_query_log(query=MagicMock(), nib_user_id=-1)
        svc.query_log_repo.add_benefit_log.assert_not_called()

    def test_app_uses_the_pk_path(self):
        with open(APP_PY, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("create_run_time_query_log(", src)
        self.assertNotIn("to_create_query_log_dto(", src)


class TestRunTimeQueryLogAllocatesIdFromSequence(unittest.TestCase):
    """query_log_table.id has no identity/trigger; the backend feeds it from
    Sequence('query_log_id_seq'). The worker's model must declare the same
    sequence or its INSERTs send NULL (ORA-01400)."""

    def test_model_id_column_uses_the_backend_sequence(self):
        from sqlalchemy import Sequence
        from src.admin.query_log.query_log_model import QueryLogTable
        col = QueryLogTable.__table__.c.id
        self.assertIsInstance(col.default, Sequence)
        self.assertEqual(col.default.name, "query_log_id_seq")
        self.assertTrue(col.primary_key)

    def test_failed_run_time_log_rolls_the_session_back(self):
        with open(APP_PY, encoding="utf-8") as f:
            src = f.read()
        i = src.index('logger.warning("Could not create run-time query log: %s", log_create_err)')
        window = src[i:i + 600]
        self.assertIn("Session.rollback()", window)
