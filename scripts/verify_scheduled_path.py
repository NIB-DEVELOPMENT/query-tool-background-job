"""RUNTIME gate for the scheduled-report path. Run INSIDE the built image.

Source-level tests prove the SQL text is schema-qualified; only the real
database can prove the qualified name RESOLVES for the account this worker
actually connects as (ORA-00942 was invisible to every test until 2026-08-20).
Read-only: a SELECT that matches no row, and a user lookup by id.

    docker run --rm -e PYTHONPATH=/app -w /app --entrypoint python \
        -v $PWD/config.py:/app/config.py \
        nibitdev/query-tool-background-job:v2-candidate scripts/verify_scheduled_path.py

Exit 0 = safe to deploy. Non-zero = do NOT deploy.
"""
import logging
import sys

logging.disable(logging.CRITICAL)

from sqlalchemy import text  # noqa: E402

from src import Session  # noqa: E402
from src.nib_user.nib_user_repo import NIBUserRepo  # noqa: E402

failures = []


def check(label, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(label)


# Do NOT import app: its module level wires RabbitMQ. Derive the name the same
# way app.py does and assert app.py's source agrees.
import os, re  # noqa: E402
from config import OracleDB  # noqa: E402
SCHEDULED_REPORT_TABLE = f"{OracleDB().userName}.scheduled_report_table"
with open(os.path.join(os.path.dirname(__file__), "..", "app.py"), encoding="utf-8") as f:
    _src = f.read()
check("app.py defines SCHEDULED_REPORT_TABLE from OracleDB().userName",
      'SCHEDULED_REPORT_TABLE = f"{OracleDB().userName}.scheduled_report_table"' in _src)
check("app.py has no bare scheduled_report_table in FROM/UPDATE",
      not re.search(r"(?:FROM|UPDATE)\s+scheduled_report_table", _src))

if SCHEDULED_REPORT_TABLE:
    who = Session.execute(text("select user from dual")).scalar()
    try:
        Session.execute(
            text(f"SELECT last_run_at, frequency, day_of_week, day_of_month, run_time, is_active "
                 f"FROM {SCHEDULED_REPORT_TABLE} WHERE id = :id"),
            {"id": -1},
        ).fetchone()
        check(f"SELECT FROM {SCHEDULED_REPORT_TABLE} resolves as {who}", True)
    except Exception as exc:  # noqa: BLE001
        check(f"SELECT FROM {SCHEDULED_REPORT_TABLE} resolves as {who}", False, str(exc).splitlines()[0])
    finally:
        Session.remove()

print("== 2. run-time query_log creation can look up the user (the NIBUser.query crash) ==")
try:
    dto = NIBUserRepo().find_by_id(nib_user_id=-1)
    check("NIBUserRepo.find_by_id executes through the Session", True, f"(no row -> {dto!r})")
except AttributeError as exc:
    check("NIBUserRepo.find_by_id executes through the Session", False, str(exc))
except Exception as exc:  # noqa: BLE001
    check("NIBUserRepo.find_by_id executes through the Session", False, str(exc).splitlines()[0])
finally:
    Session.remove()

print("== 3. run-time query_log rows can allocate an id (backend sequence, visible to this account) ==")
try:
    from sqlalchemy import Sequence
    from src.admin.query_log.query_log_model import QueryLogTable
    col = QueryLogTable.__table__.c.id
    check("QueryLogTable.id default is Sequence(query_log_id_seq)",
          isinstance(col.default, Sequence) and col.default.name == "query_log_id_seq")
    row = Session.execute(text(
        "select count(*) from all_sequences where sequence_name = 'QUERY_LOG_ID_SEQ' "
        "and sequence_owner = upper(:o)"), {"o": OracleDB().userName}).scalar()
    check("sequence exists and is visible to this account", row == 1, f"(matches={row})")
except Exception as exc:  # noqa: BLE001
    check("query_log id allocation", False, str(exc).splitlines()[0])
finally:
    Session.remove()

print()
if failures:
    print(f"RESULT: FAIL -- {failures}")
    sys.exit(1)
print("RESULT: PASS -- scheduled-report path is functional for this worker's DB account")
