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
session= orm.scoped_session(orm.sessionmaker(bind=engine))
session.configure(bind=engine)
Session=session()