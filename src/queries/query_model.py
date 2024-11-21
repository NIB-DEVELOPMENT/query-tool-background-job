from sqlalchemy import *
from src import engine, base

class QueryTable(base):
    __tablename__ = 'query_table'
    __table_args__ = ({'schema': 'nib_query_tool_ls_1', 'autoload_with': engine, "extend_existing" : True})