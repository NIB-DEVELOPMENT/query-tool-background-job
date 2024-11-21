from dataclasses import dataclass
from src.queries.query_model import QueryTable
from src.queries.dto.query_dto import QueryDTO
from src.queries.dto.create_query_dto import CreateQueryDTO
from src.queries.dto.query_result_dto import QueryResultDTO
from src.queries.dto.execute_query_dto import ExecuteQueryDTO
from sqlalchemy.sql import text
from sqlalchemy.engine.cursor import CursorResult
from typing import List
from src import Session, engine

@dataclass
class QueryRepo:
    db = Session

    def get_query(self, query_id: int) -> QueryDTO:
        query = self.db.query(QueryTable).filter(QueryTable.id == query_id).first()
        return self.to_query_dto(query)

    def _get_query(self, query_id: int) -> QueryTable:
        query = QueryTable.query.filter(QueryTable.id == query_id).first()
        return query


    def update_query(self, query_id: int, query_dto: CreateQueryDTO) -> QueryDTO:
        query = QueryTable.query.filter(QueryTable.id == query_id).first()
        query.name = query_dto.name
        query.file_path = query_dto.file_path
        self.db.commit()
        return self.to_query_dto(query)

    def delete_query(self, query_id: int) -> None:
        query = QueryTable.query.filter(QueryTable.id == query_id).first()
        self.db.delete(query)
        self.db.commit()
        return self.to_query_dto(query)

    def get_query_params(self, query: str) -> list:
        params_name = []
        if "Parameters:" in query:
            comment: str = (query.split("Parameters:")[1].split("*/")[0]).splitlines()[
                0
            ]
            params_name = comment.rsplit(",")
        return params_name


    def get_query_results(self, query: str, execute_dto: ExecuteQueryDTO) -> list:
        paginated_query = self.paginate_query(
            query=query, page=execute_dto.page, per_page=execute_dto.per_page
        )
        results: CursorResult = self.db.session.execute(
            text(paginated_query), execute_dto.query_params
        )
        return self.to_query_result_dto(results=results)

    def paginate_query(self, query: str, page: int, per_page: int) -> str:
        query = (
            "select * \n from(\nselect qy.*, COUNT ( * ) OVER () total from ("
            + query
            + "\n )qy \n) \n offset  "
            + str((page - 1) * per_page)
            + " rows \nfetch next "
            + str(per_page)
            + " rows only"
        )
        return query

    def get_query_params(self, query: str) -> list:
        params_name = []
        if "Parameters:" in query:
            comment: str = (query.split("Parameters:")[1].split("*/")[0]).splitlines()[
                0
            ]
            params_name = comment.rsplit(",")
        return params_name

    def to_query_result_dto(self, results: CursorResult) -> QueryResultDTO:
        rows = results._fetchall_impl()
        query_result: QueryResultDTO = QueryResultDTO(
            column_names=list(results.keys()._keys),
            rows=rows,
        )
        if rows:
            query_result.total_count = rows[0][-1]
        return query_result

    def to_query_dto(self, query: QueryTable) -> QueryDTO:
        query_dto: QueryDTO = None
        if query:
            query_dto = QueryDTO(
                id=query.id,
                name=query.name,
                file_path=query.file_path,
                department=query.department,
            )
        return query_dto

    def to_query_role_dtos(self, queries: List[QueryTable]) -> List[QueryDTO]:
        query_role_dtos: list = []
        for query in queries:
            query_role_dtos.append(
                QueryDTO(
                    id=query.id,
                    name=query.name,
                    file_path=query.file_path,
                    department=query.department,
                )
            )
        return query_role_dtos

    def execute_query(self, query: str, execute_dto: ExecuteQueryDTO) -> list:
            results: CursorResult = self.db.execute(
                text(query), execute_dto.query_params
            )
            return self.to_query_result_dto(results=results)