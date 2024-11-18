import sqlalchemy as sa
from config import OracleDB
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declarative_base

base=declarative_base()
engine=sa.create_engine(f"oracle+oracledb://{OracleDB.dbaUser}:{OracleDB.dbaPassword}@{OracleDB.host}:{OracleDB.port}?service_name={OracleDB.sid}",
                        echo=True)
base.metadata.bind = engine
session= orm.scoped_session(orm.sessionmaker(bind=engine))
session.configure(bind=engine)
Session=session()