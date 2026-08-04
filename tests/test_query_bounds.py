"""
Tests for DS-07 worker execution bounds (poison-loop root fix).

Scenarios per the session spec:
1. Timeout breach  -> QueryBoundsExceeded raised (callback marks FAILED + acks)
2. Row-cap breach  -> QueryBoundsExceeded raised during fetch streaming
3. Redelivered + terminal log row -> skip (ack via finally, no reprocessing)
4. Happy path unchanged

Convention (see test_callback_session_management.py): callback() lives inside
`if __name__ == '__main__':` so the callback contract is asserted at source
level; units (query_bounds, repo streaming, timeout mapping) are tested
directly. src.query_bounds is standalone (no src/config import needed).
"""
import importlib.util
import os
import re
import sys
import unittest
from unittest.mock import MagicMock

HERE = os.path.dirname(__file__)
APP_PY = os.path.join(HERE, '..', 'app.py')
REPO_PY = os.path.join(HERE, '..', 'src', 'queries', 'query_repo.py')
INIT_PY = os.path.join(HERE, '..', 'src', '__init__.py')


def _load_query_bounds():
    spec = importlib.util.spec_from_file_location(
        "query_bounds", os.path.join(HERE, '..', 'src', 'query_bounds.py')
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


qb = _load_query_bounds()


class TestWorkerLimitsDefaults(unittest.TestCase):
    """Config-driven with hard defaults (gate: config_defaults)."""

    def test_defaults_without_config(self):
        # No config module importable in tests -> code defaults.
        self.assertEqual(qb.worker_limits(), (1800, 500_000))

    def test_config_values_win(self):
        fake_config = MagicMock()
        fake_config.WorkerLimits.QUERY_TIMEOUT_SECONDS = 900
        fake_config.WorkerLimits.QUERY_ROW_CAP = 100
        sys.modules['config'] = fake_config
        try:
            self.assertEqual(qb.worker_limits(), (900, 100))
        finally:
            del sys.modules['config']

    def test_config_missing_class_falls_back(self):
        fake_config = MagicMock(spec=[])  # no WorkerLimits attribute
        sys.modules['config'] = fake_config
        try:
            self.assertEqual(qb.worker_limits(), (1800, 500_000))
        finally:
            del sys.modules['config']


class TestTimeoutBreach(unittest.TestCase):
    """Scenario 1: oracledb call-timeout kill -> QueryBoundsExceeded."""

    def test_timeout_error_family_detected(self):
        for code in ("DPY-4024", "ORA-03156", "ORA-01013"):
            err = Exception(f"boom: {code}: call timeout exceeded")
            self.assertTrue(qb.is_call_timeout_error(err), code)

    def test_wrapped_orig_detected(self):
        err = Exception("DatabaseError")
        err.orig = Exception("DPY-4024: call timeout of 1800000 ms exceeded")
        self.assertTrue(qb.is_call_timeout_error(err))

    def test_other_errors_not_matched(self):
        err = Exception("ORA-00942: table or view does not exist")
        self.assertFalse(qb.is_call_timeout_error(err))

    def test_repo_maps_timeout_to_bounds_exceeded(self):
        """Source-level: execute_query wraps execution and re-raises the
        call-timeout family as QueryBoundsExceeded."""
        with open(REPO_PY) as f:
            source = f.read()
        body = source.split("def execute_query(")[1]
        self.assertIn("is_call_timeout_error", body)
        self.assertIn("QueryBoundsExceeded", body)
        self.assertIn('kind="timeout"', body)


class TestRowCapBreach(unittest.TestCase):
    """Scenario 2: streaming fetch past the cap -> QueryBoundsExceeded."""

    @staticmethod
    def _fake_results(total_rows):
        results = MagicMock()
        remaining = [(i, i) for i in range(total_rows)]

        def fetchmany(n):
            nonlocal remaining
            chunk, remaining = remaining[:n], remaining[n:]
            return chunk

        results.fetchmany.side_effect = fetchmany
        results.keys.return_value._keys = ["A", "B"]
        return results

    def _to_dto(self, results, row_cap):
        # Exercise the real to_query_result_dto without importing src
        # (engine creation needs the mounted config). Extract the method and
        # run it against a stub self.
        with open(REPO_PY) as f:
            source = f.read()
        method_src = source.split("def to_query_result_dto(")[1]
        method_src = "def to_query_result_dto(" + method_src.split("\n    def ")[0]
        ns = {
            "QueryBoundsExceeded": qb.QueryBoundsExceeded,
            "QueryResultDTO": lambda **kw: MagicMock(**kw),
            "CursorResult": object,
        }
        exec("from unittest.mock import MagicMock", ns)
        exec(re.sub(r"^    ", "", method_src, flags=re.M), ns)
        return ns["to_query_result_dto"](MagicMock(), results, row_cap=row_cap)

    def test_breach_raises(self):
        with self.assertRaises(qb.QueryBoundsExceeded) as ctx:
            self._to_dto(self._fake_results(150), row_cap=100)
        self.assertEqual(ctx.exception.kind, "row_cap")
        self.assertEqual(ctx.exception.limit, 100)

    def test_under_cap_passes(self):
        dto = self._to_dto(self._fake_results(50), row_cap=100)
        self.assertEqual(len(dto.rows), 50)

    def test_exception_message_carries_details(self):
        exc = qb.QueryBoundsExceeded(kind="row_cap", limit=500_000, query_id=288)
        self.assertIn("row_cap", str(exc))
        self.assertIn("500000", str(exc))
        self.assertIn("288", str(exc))


class TestRedeliveryGuard(unittest.TestCase):
    """Scenario 3: redelivered + terminal row -> skip; guard is a backstop."""

    def setUp(self):
        with open(APP_PY) as f:
            self.source = f.read()

    def test_guard_present_before_executing_update(self):
        guard = self.source.find("method.redelivered")
        executing = self.source.find('status="EXECUTING"')
        self.assertGreater(guard, 0, "redelivery guard missing from callback")
        self.assertLess(guard, executing,
                        "guard must run BEFORE the EXECUTING status update")

    def test_guard_checks_terminal_states(self):
        self.assertIn('prior_status in ("FAILED", "COMPLETE")', self.source)

    def test_guard_skips_via_return_so_finally_acks(self):
        guard_block = self.source.split("method.redelivered")[1][:2000]
        self.assertIn("return", guard_block)
        self.assertIn("add_breadcrumb", guard_block)

    def test_guard_lookup_failure_processes_normally(self):
        guard_block = self.source.split("method.redelivered")[1][:2000]
        self.assertIn("except Exception as guard_err", guard_block)
        self.assertIn("prior_status = None", guard_block)


class TestAckDiscipline(unittest.TestCase):
    """Gate no_unacked_failure_path: exactly one ack, in finally."""

    def setUp(self):
        with open(APP_PY) as f:
            self.source = f.read()

    def test_single_ack_in_finally(self):
        acks = self.source.count("basic_ack")
        self.assertEqual(acks, 1, "callback must ack in exactly one place")
        finally_pos = self.source.find("finally:")
        ack_pos = self.source.find("basic_ack")
        self.assertGreater(ack_pos, finally_pos,
                           "the single ack must live in the finally block")

    def test_no_nack_or_reject(self):
        self.assertNotIn("basic_nack", self.source)
        self.assertNotIn("basic_reject", self.source)


class TestHappyPathUnchanged(unittest.TestCase):
    """Scenario 4: no-cap path still uses the original fetch; engine keeps
    pool_pre_ping/pool_recycle (gate pre_ping_inherited) and the default
    timeout is a connect-event in ms (gate timeout_mechanism)."""

    def test_no_cap_uses_original_fetchall(self):
        with open(REPO_PY) as f:
            source = f.read()
        self.assertIn("_fetchall_impl", source,
                      "uncapped path must keep the original fetch behavior")

    def test_engine_pool_settings_inherited(self):
        with open(INIT_PY) as f:
            source = f.read()
        self.assertIn("pool_pre_ping=True", source)
        self.assertIn("pool_recycle=1800", source)

    def test_default_timeout_is_connect_event_in_ms(self):
        with open(INIT_PY) as f:
            source = f.read()
        self.assertIn('listens_for(engine, "connect")', source)
        self.assertIn("call_timeout = worker_limits()[0] * 1000", source)
        self.assertNotIn("call_timeout=", source.split("create_engine")[1].split(")")[0],
                         "call_timeout must NEVER be a connect()/create_engine kwarg")


if __name__ == "__main__":
    unittest.main()
