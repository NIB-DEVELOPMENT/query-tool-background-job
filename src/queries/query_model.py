from sqlalchemy import *
from src import engine, base
from config import OracleDB

class QueryTable(base):
    __tablename__ = 'query_table'
    __table_args__ = ({'schema': OracleDB().userName, 'autoload_with': engine, "extend_existing" : True})