from sqlalchemy import *
from src import engine, base

class NIBUser(base):
    __tablename__ = 'nib_users'
    __table_args__ = ({'schema': 'nib_admin_auth','autoload_with': engine, "extend_existing" : True})
    
