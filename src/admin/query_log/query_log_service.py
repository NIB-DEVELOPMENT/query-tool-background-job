from src.admin.query_log.dto.create_query_log_dto import CreateQueryLogDTO
from src.admin.query_log.enum.query_log_exception_messages import QueryLogException
from src.admin.query_log.query_log_repo import QueryLogRepo
from src.nib_user.nib_user_repo import NIBUserRepo
from werkzeug.exceptions import BadRequest
from src.admin.query_log.dto.query_log_search_criteria_dto import (
    QueryLogSearchCriteriaDTO,
)
from src.queries.dto.query_dto import QueryDTO


class QueryLogService:
    def __init__(self):
        self.query_log_repo = QueryLogRepo()
        self.nib_user_repo = NIBUserRepo()

    def to_create_query_log_dto(
        self, log_data: QueryDTO, user_id: int
    ) -> CreateQueryLogDTO:
        nib_user_dto = self.nib_user_repo.find_by_user_id(user_id=user_id)
        return CreateQueryLogDTO(user=nib_user_dto, query=log_data)

    def search_query_logs(self, query_log_search_criteria: QueryLogSearchCriteriaDTO):
        queries, total = self.query_log_repo.filter_query_log(query_log_search_criteria)
        if not queries:
            raise BadRequest(QueryLogException.NO_QUERY_LOGS_FOUND.value)
        return queries, total

    def create_query_log(self, query_log_dto: CreateQueryLogDTO):
        if not query_log_dto:
            raise BadRequest(QueryLogException.QUERY_LOG_NOT_SENT.value)
        return self.query_log_repo.add_benefit_log(query_log_dto)

    def update_query_log(self, log_id: int, status: str):
        if not log_id:
            raise BadRequest(QueryLogException.QUERY_ID_NOT_SENT.value)
        return self.query_log_repo.update_query_log(
            query_id=log_id, status=status
        )
