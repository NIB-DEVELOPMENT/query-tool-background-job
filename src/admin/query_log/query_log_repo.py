from dataclasses import dataclass
from src.admin.query_log.query_log_model import QueryLogTable
from src.queries.query_model import QueryTable
from src.admin.query_log.dto.create_query_log_dto import CreateQueryLogDTO
from src.admin.query_log.dto.query_log_dto import QueryLogDTO
from src.nib_user.nib_user_model import NIBUser
from src.admin.query_log.dto.date_range_dto import DateRangeDTO
from src.admin.query_log.dto.query_log_search_criteria_dto import (
    QueryLogSearchCriteriaDTO,
)
from src import Session

@dataclass
class QueryLogRepo:
    db = Session

    def add_benefit_log(self, query_log_dto: CreateQueryLogDTO) -> QueryLogDTO:
        query_log = QueryLogTable(
            user_id=query_log_dto.user.id,
            query_id=query_log_dto.query.id,
            user_name=query_log_dto.user.user_name,
            status=query_log_dto.status,
            inserted_by=query_log_dto.user.user_name,
        )
        self.db.add(query_log)
        self.db.commit()
        return self.to_query_log_dto(query_log)

    def filter_query_log(
        self, query_log_search_criteria: QueryLogSearchCriteriaDTO
    ) -> list:
        query_log = (
            self.db.query(QueryLogTable)
            .join(NIBUser, NIBUser.id == QueryLogTable.user_id)
            .join(QueryTable, QueryTable.id == QueryLogTable.query_id)
        )
        for attr, value in query_log_search_criteria.__dict__.items():
            if "user_name" in attr and value:
                query_log = query_log.filter(
                    getattr(getattr(NIBUser, attr), "ilike")(f"%{value}%")
                )
                continue

            if "query_id" == attr and value:
                query_log = query_log.filter(getattr(QueryTable, attr) == value)
                continue

            if attr == "inserted_date":
                date_range: DateRangeDTO = value
                if date_range.start:
                    query_log = query_log.filter(
                        getattr(QueryLogTable, attr) >= date_range.start
                    )
                if date_range.end:
                    query_log = query_log.filter(getattr(QueryLogTable, attr) <= date_range.end)
                continue

        query_logs = query_log.order_by(QueryLogTable.inserted_date.asc())
        query_dtos = self.to_query_log_dtos(query_logs)
        return query_dtos, query_logs.total

    def update_query_log(
        self, query_id: int, status: str
    ) -> QueryLogDTO:
        query_log = self.db.query(QueryLogTable).filter_by(id=query_id).first()
        query_log.status = status
        self.db.commit()
        return self.to_query_log_dto(query_log)

    def to_query_log_dto(self, query_log: QueryLogTable) -> QueryLogDTO:
        return QueryLogDTO(
            id=query_log.id,
            user_id=query_log.user_id,
            query_id=query_log.query_id,
            user_name=query_log.user_name,
            status=query_log.status,
        )

    def to_query_log_dtos(self, query_logs: list) -> list:
        return [self.to_query_log_dto(query_log) for query_log in query_logs]
