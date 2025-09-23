import os
import pathlib
from src.queries.query_repo import QueryRepo
from src.queries.dto.query_dto import QueryDTO
from src.queries.dto.create_query_dto import CreateQueryDTO
from src.queries.dto.validated_query_dto import ValidatedQueryDTO
from werkzeug.exceptions import BadRequest
from src.queries.enums.exception_message import QueryException
from config import FileRepo
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from src.database.SQLReader import SQLReader
from src.queries.dto.execute_query_dto import ExecuteQueryDTO
from src.nib_user.nib_user_service import NIBUserService


class QueryService:
    query_repo = QueryRepo()
    base_path = FileRepo.path
    sql_reader = SQLReader()
    nib_user_service = NIBUserService()

    def _allowed_extensions(self, query_upload: FileStorage) -> bool:
        extensions = {".sql"}
        file_extension = pathlib.Path(query_upload.filename).suffix.lower()
        if file_extension not in extensions:
            raise BadRequest(QueryException.INVALID_FILE_EXTENSION.value)

    def _validate_query(self, query_data: CreateQueryDTO) -> ValidatedQueryDTO:
        ValidatedQueryDTO.validated = False
        if not query_data.name:
            raise BadRequest(QueryException.QUERY_NAME_NOT_PRESENT.value)
        if not query_data.query_upload:
            raise BadRequest(QueryException.QUERY_FILE_NOT_PRESENT.value)
        self._allowed_extensions(query_data.query_upload)
        query_name = (
            query_data.name
            + pathlib.Path(query_data.query_upload.filename).suffix.lower()
        )
        return ValidatedQueryDTO(
            validated=True,
            query_name=query_name,
            query_upload=query_data.query_upload,
            department=query_data.department,
        )

    def get_query_by_id(self, query_id: int) -> QueryDTO:
        query: QueryDTO = self.query_repo.get_query(query_id=query_id)
        if not query:
            raise BadRequest(QueryException.QUERY_DOESNT_EXIST.value)
        return query

    def get_query(self, query_id: int) -> QueryDTO:
        query = self.get_query_by_id(query_id=query_id)
        script = self.sql_reader.getSQL(scriptPath=query.file_path)
        params: list = self.query_repo.get_query_params(query=script)
        if params:
            params = dict((s.rsplit(":")[1], s.rsplit(":")[0]) for s in params)
            query.query_params = params
        return query

    def add_query(self, query_data: CreateQueryDTO) -> QueryDTO:
        valid_query: ValidatedQueryDTO = self._validate_query(query_data)
        query: CreateQueryDTO = self._save_query_file(validated_query=valid_query)
        return self.query_repo.add_query(query_dto=query)

    def update_query(self, query_id: int, query_data: CreateQueryDTO) -> QueryDTO:
        if not query_data.name:
            raise BadRequest(QueryException.QUERY_NAME_NOT_PRESENT.value)
        valid_query: ValidatedQueryDTO = self._validate_query(query_data)
        query: CreateQueryDTO = self._update_query_file(
            validated_query=valid_query, query_id=query_id
        )
        return self.query_repo.update_query(query_id=query_id, query_dto=query)

    def delete_query(self, query_id: int) -> None:
        query = self.query_repo.delete_query(query_id=query_id)
        if not self.delete_query_file(query.file_path):
            raise BadRequest(QueryException.QUERY_FILE_NOT_DELETED.value)
        return query

    def validate_query_id_present(self, query_id: int) -> bool:
        if not query_id:
            raise BadRequest(QueryException.Query_ID_NOT_PRESENT.value)
        return True

    def validate_query_doesnt_exists(self, query_id: int) -> bool:
        query = self.query_repo._get_query(query_id=query_id)
        if not query:
            raise BadRequest(QueryException.QUERY_DOESNT_EXIST.value)
        return True

    def validate_query_exists(self, query_id: int) -> bool:
        query = self.query_repo._get_query(query_id=query_id)
        if not query:
            raise BadRequest(QueryException.QUERY_DOESNT_EXIST.value)
        return True

    def _save_query_file(self, validated_query: ValidatedQueryDTO):
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)
        secure_file = secure_filename(validated_query.query_name)
        file_path = os.path.join(self.base_path, secure_file)
        if os.path.exists(file_path):
            raise BadRequest(QueryException.QUERY_EXISTS_WITH_NAME.value)
        validated_query.query_upload.save(file_path)
        return CreateQueryDTO(
            name=validated_query.query_name,
            file_path=file_path,
            department=validated_query.department,
            query_upload=validated_query.query_upload,
        )

    def _get_file_path(self, secure_file: str, department: str):
        file_path = os.path.join(self.base_path, department, secure_file)
        return file_path

    def _update_query_file(self, query_id: int, validated_query: ValidatedQueryDTO):
        if not os.path.exists(self.base_path):
            raise BadRequest(QueryException.QUERY_DOESNT_EXIST.value)
        secure_file = secure_filename(validated_query.query_name)
        file_path = os.path.join(self.base_path, secure_file)
        query = self.get_query(query_id=query_id)
        self.delete_query_file(file_path=query.file_path)
        validated_query.query_upload.save(file_path)
        return CreateQueryDTO(
            name=validated_query.query_name,
            file_path=file_path,
            query_upload=validated_query.query_upload,
        )

    def delete_query_file(self, file_path: str) -> None:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False

    def get_all_queries_by_department(self, department_id: int, page: int) -> list:
        queries, total = self.query_repo.get_all_queries_by_department(
            department_id=department_id, page=page
        )
        return queries, total

    def get_query_results(self, execute_dto: ExecuteQueryDTO) -> list:
        query_dto: QueryDTO = self.get_query_by_id(query_id=execute_dto.query_id)
        if not os.path.isfile(query_dto.file_path):
            raise BadRequest(QueryException.QUERY_FILE_NOT_AVAILABLE.value)
        query = self.sql_reader.getSQL(scriptPath=query_dto.file_path)
        return self.query_repo.get_query_results(query=query, execute_dto=execute_dto)

    def to_execute_query_dto(self, query: dict) -> ExecuteQueryDTO:
        execute_query_dto = ExecuteQueryDTO(
            first_name=query["first_name"],
            query_id=query["id"],
            name=query["name"],
            user_id=query["user_id"],
            file_path=query["file_path"],
            query_params=query["query_params"],
            email=query["email_address"],
            department=query["department"],
        )
        return execute_query_dto

    def get_query_report(self, query_id: int, params: dict) -> QueryDTO:
        query = self.get_query_by_id(query_id=query_id)
        if params:
            query.query_params = params
        return query

    def get_queries_by_user_role(
        self, user_roles: list, page: int, per_page: int
    ) -> list:
        queries, total = self.query_repo.get_queries_by_user_role(
            user_roles=user_roles, page=page, per_page=per_page
        )
        return queries, total
    
    def execute_query_from_rabbitmq(self, query: ExecuteQueryDTO) -> list:
        if not os.path.isfile(query.file_path):
            raise BadRequest(QueryException.QUERY_FILE_NOT_AVAILABLE.value)
        valid_query = self.sql_reader.getSQL(scriptPath=query.file_path)
        return self.query_repo.execute_query(query=valid_query, execute_dto=query)
    
