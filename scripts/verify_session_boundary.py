"""RUNTIME gate for the per-message session boundary. Run INSIDE the built image.

Source-level tests cannot catch what broke prod on 2026-08-17: they asserted
`Session.remove()` appears in app.py, which it did -- but `Session` was a
materialised Session instance with no .remove(), so the callback raised
AttributeError on the first message and every worker dropped out of
start_consuming(). "The line is present" and "the line works" are different
claims. This asserts the second.

It proves the actual failure mode and the actual recovery against the real
database:

  1. Session exposes the API the callback calls (remove/rollback/execute)
  2. the repos' `db` attribute is the same object, so a reset reaches them
  3. a failed statement really does poison the session (PendingRollbackError)
  4. rollback + remove really does recover it

Read-only: the only statement executed on purpose is a deliberate syntax error
against a non-existent table. Nothing is written.

Usage (must be inside the image, with config.py present):
    docker run --rm -e PYTHONPATH=/app -w /app --entrypoint python \
        nibitdev/query-tool-background-job:prod scripts/verify_session_boundary.py

Exit 0 = safe to deploy. Non-zero = do NOT deploy.
"""
import sys

from sqlalchemy import text
from sqlalchemy.exc import PendingRollbackError

from src import Session

failures = []


def check(label, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(label)


print("== 1. Session exposes the API the callback uses ==")
for attr in ("remove", "rollback", "execute"):
    check(f"Session.{attr} exists", callable(getattr(Session, attr, None)))

print("== 2. repos share the same session object (a reset must reach them) ==")
try:
    from src.queries.query_repo import QueryRepo
    check("QueryRepo.db is Session", QueryRepo.db is Session)
except Exception as exc:                                        # noqa: BLE001
    check("QueryRepo import", False, str(exc).splitlines()[0])

print("== 3. baseline query works ==")
try:
    check("select 1", Session.execute(text("select 1 from dual")).scalar() == 1)
except Exception as exc:                                        # noqa: BLE001
    check("select 1", False, str(exc).splitlines()[0])

print("== 4. a failed statement poisons the session (the real failure mode) ==")
try:
    Session.execute(text("select * from a_table_that_does_not_exist_xyz"))
    check("bad statement raises", False, "it did not raise")
except Exception:
    check("bad statement raises", True)

poisoned = False
try:
    Session.execute(text("select 1 from dual"))
    print("  NOTE  session was not left poisoned on this driver/version")
except PendingRollbackError:
    poisoned = True
    check("session is now poisoned (PendingRollbackError)", True)
except Exception as exc:                                        # noqa: BLE001
    print(f"  NOTE  follow-up raised {type(exc).__name__}, treating as poisoned")
    poisoned = True

print("== 5. rollback + remove recovers it (what the fix relies on) ==")
try:
    Session.rollback()
except Exception as exc:                                        # noqa: BLE001
    print(f"  NOTE  rollback() itself raised ({type(exc).__name__}) "
          f"-- exactly why remove() is the fallback")
Session.remove()

try:
    check("query works again after reset",
          Session.execute(text("select 1 from dual")).scalar() == 1)
except Exception as exc:                                        # noqa: BLE001
    check("query works again after reset", False, str(exc).splitlines()[0])
finally:
    Session.remove()

if poisoned:
    print("  (the poisoning was reproduced, so the recovery above is meaningful)")

print()
if failures:
    print(f"RESULT: FAIL -- {len(failures)} check(s) failed: {failures}")
    sys.exit(1)
print("RESULT: PASS -- session boundary is functional; safe to deploy")
