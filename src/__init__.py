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
Session = orm.scoped_session(session_factory)

from src.query_bounds import worker_limits


# DS-07: default hard call timeout on every pooled connection. oracledb
# REJECTS call_timeout as a connect() kwarg (crash-loops workers — ee34c57);
# the attribute must be set per-connection, in MILLISECONDS. Tier-carried
# timeouts (query_repo) overwrite this per execution when present.
@sa.event.listens_for(engine, "connect")
def _apply_default_call_timeout(dbapi_conn, _connection_record):
    dbapi_conn.call_timeout = worker_limits()[0] * 1000