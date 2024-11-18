from src.database.baseModel import db

class NIBUser(db.Model):
    __tablename__ = 'nib_users'
    __table_args__ = ({'schema': 'nib_admin_auth','autoload_with': db.engine, "extend_existing" : True})
    
