from src.database.baseModel import db, BaseModel

class QueryTable(BaseModel):
    id = db.Column(
        db.Integer, db.Sequence('query_id_seq'), primary_key=True
        )
    name = db.Column(
        db.String(70),
        nullable=False,
        unique=False,
    )
    file_path = db.Column(
        db.String(250),
        nullable=False,
        unique=True
    )
    department = db.Column(
        db.String(250),
        nullable=False,
        unique=True
    )
    query_role = db.relationship(
        "QueryRoleTable",
        back_populates="queries"
    )