from dataclasses import dataclass
from src.queries.query_model import QueryTable
from src.queries.dto.query_dto import QueryDTO
from src.queries.dto.create_query_dto import CreateQueryDTO
from src.queries.dto.query_result_dto import QueryResultDTO
from src.queries.dto.execute_query_dto import ExecuteQueryDTO
from sqlalchemy.sql import text
from sqlalchemy.engine.cursor import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from src import Session, engine
from src.query_bounds import QueryBoundsExceeded, is_call_timeout_error, worker_limits

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

    def to_query_result_dto(
        self, results: CursorResult, row_cap: int = None, query_id: int = None
    ) -> QueryResultDTO:
        if row_cap:
            # DS-07 backstop: stream the fetch and fail fast past the cap
            # instead of materializing an unbounded list (256M container).
            # Tier-capped queries are already ROWNUM-limited upstream and
            # never reach this branch.
            rows = []
            while True:
                chunk = results.fetchmany(10_000)
                if not chunk:
                    break
                rows.extend(chunk)
                if len(rows) > row_cap:
                    raise QueryBoundsExceeded(
                        kind="row_cap", limit=row_cap, query_id=query_id
                    )
        else:
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

    def execute_query(
        self, query: str, execute_dto: ExecuteQueryDTO, row_cap_backstop: int = None
    ) -> list:
            # Apply Oracle server-side timeout if specified (hard-kills runaway
            # queries). Overrides the engine-level default set by the connect
            # event in src/__init__.py; without a tier value the default stands.
            if execute_dto.timeout_seconds:
                try:
                    raw_conn = self.db.connection().connection
                    dbapi_conn = raw_conn.dbapi_connection if hasattr(raw_conn, "dbapi_connection") else raw_conn
                    if hasattr(dbapi_conn, "call_timeout"):
                        dbapi_conn.call_timeout = execute_dto.timeout_seconds * 1000  # ms
                except Exception:
                    pass  # Timeout not critical — continue without it

            try:
                results: CursorResult = self.db.execute(
                    text(query), execute_dto.query_params
                )
                return self.to_query_result_dto(
                    results=results, row_cap=row_cap_backstop,
                    query_id=execute_dto.query_id,
                )
            except SQLAlchemyError as err:
                # DS-07: surface a call-timeout kill as a controlled bounds
                # failure so the callback marks the row FAILED and acks —
                # never a redelivery loop.
                if is_call_timeout_error(err):
                    raise QueryBoundsExceeded(
                        kind="timeout",
                        limit=execute_dto.timeout_seconds or worker_limits()[0],
                        query_id=execute_dto.query_id,
                    ) from err
                raise