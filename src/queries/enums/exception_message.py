from enum import Enum


class QueryException(Enum):
    QUERY_ID_NOT_PRESENT = "Query ID not present"
    QUERY_DOESNT_EXIST = "No query found with the given ID"
    INVALID_FILE_EXTENSION = "Invalid file extension. Only .sql files are allowed"
    QUERY_EXISTS_WITH_NAME = "Query already exists with the given name"
    QUERY_ALREADY_EXIST = "Query already exists"
    QUERY_FILE_NOT_DELETED = "Query file not deleted"
    QUERY_FILE_NOT_AVAILABLE = "Query file not available"
    QUERY_PARAMS_NOT_SENT = "The query_params key was not sent"
    QUERY_USER_NOT_SENT = "The user_id key was not sent"
    QUERY_USER_EMAIL_DOESNT_EXIST = "Query user does not have an email"
    QUERY_USER_DOESENT_EXIST = "Query user does not exist"
    QUERY_REPORT_ID_NOT_SENT = "The report_id key was not sent"
    QUERY_NAME_NOT_SENT = "The query_name key was not sent"
    QUERY_UPLOAD_NOT_SENT = "The query_upload key was not sent"
    QUERY_FILE_NOT_PRESENT = "Query file not present"
