from src import db

class BaseModel(db.Model):
    __abstract__ = True

    inserted_by = db.Column(
        db.String(50)
    )
    inserted_date = db.Column(
        db.DateTime,
        default=db.func.now()
    )
    updated_by = db.Column(
        db.String(50)
    )
    updated_date = db.Column(
        db.DateTime,
        onupdate=db.func.now()
    )