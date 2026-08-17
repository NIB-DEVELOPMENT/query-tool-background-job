import sqlalchemy as sa
from config import OracleDB
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declarative_base

base=declarative_base()
engine = sa.create_engine(
    f"oracle+oracledb://{OracleDB.dbaUser}:{OracleDB.dbaPassword}@"
    f"{OracleDB.host}:{OracleDB.port}?service_name={OracleDB.sid}",
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=3,
    max_overflow=2,
    echo=True,
)
base.metadata.bind = engine
session_factory = orm.sessionmaker(bind=engine)

# Export the scoped_session ITSELF, not a materialised session.
#
# This used to be `Session = session()`, which called the registry and handed
# every importer one fixed Session object for the life of the process. Two
# consequences, both of which cost us incident 68444:
#
#   1. `Session` had no .remove(), so there was no way to reset the session
#      between messages -- the API the fix needs did not exist.
#   2. Even calling `session.remove()` on the registry would not have helped:
#      the repos bind `db = Session` at class-definition time, so they would
#      still hold a reference to the DISCARDED object.
#
# A scoped_session proxies execute/query/rollback/commit to the current
# thread-local session, so `db = Session` keeps working unchanged while
# Session.remove() genuinely resets it for every holder. This is exactly the
# shape query-tool-background-job:v2 has been running in production since
# 2026-08-05 (staging d4d2e52), so it is proven, not novel.
Session = orm.scoped_session(session_factory)

# Backwards-compatible alias: older code referred to the registry as `session`.
session = Session