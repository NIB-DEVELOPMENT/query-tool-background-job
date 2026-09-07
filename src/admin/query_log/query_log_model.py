from sqlalchemy import *
from src import engine, base
from config import OracleDB


class QueryLogTable(base):
    __tablename__ = 'query_log_table'
    __table_args__ = ({'schema': OracleDB().userName, 'autoload_with': engine, "extend_existing" : True})
    # The PK is fed by the backend's Sequence("query_log_id_seq") -- there is no
    # identity column and no trigger, so reflection sees a plain INTEGER with no
    # default and any INSERT from this side sends NULL (ORA-01400, 2026-09-07).
    # Declaring the same sequence here makes the worker's run-time log rows
    # allocate ids exactly like the backend's pre-created ones.
    id = Column(Integer, Sequence("query_log_id_seq", schema=OracleDB().userName), primary_key=True)
