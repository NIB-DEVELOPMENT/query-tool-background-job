from enum import Enum


class QueryLogException(Enum):
    QUERY_ID_NOT_SENT = "The query_id was not sent"
    QUERY_LOG_NOT_SENT = "The query log was not sent"
