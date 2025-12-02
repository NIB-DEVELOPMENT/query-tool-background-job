import csv
import os
import logging
from config import FileRepo, QueryToolBackend
from src.queries.dto.execute_query_dto import ExecuteQueryDTO
from src.document_save.filename_service import FilenameService
from datetime import datetime

logger = logging.getLogger(__name__)


class DocumentSaveService:
    base_path = FileRepo.base_drive
    def save_to_csv(self, results, query:ExecuteQueryDTO):
        """
        Save query results to a CSV file with an improved filename format.

        The filename includes timestamp, user ID, query name, and parameters for
        easy identification and chronological sorting.

        Args:
            results: Query results object with 'column_names' and 'rows' attributes
            query (ExecuteQueryDTO): Query metadata including user_id, name,
                                     query_params, and query_id

        Returns:
            str: Absolute file path to the saved CSV file

        Raises:
            Exception: Re-raises any file operation exceptions for Sentry capture

        Example:
            >>> results = QueryResults(column_names=['id', 'name'], rows=[[1, 'John']])
            >>> path = service.save_to_csv(results, query_dto)
            >>> print(path)
            'data_repository/query_tool/query_results/31688/123/20251201-143022-31688-Report-dept_HR.csv'
        """
        # Generate filename using FilenameService
        filename = FilenameService.generate_filename(
            user_id=query.user_id,
            query_name=query.name,
            query_params=query.query_params,
            timestamp=datetime.now()
        )

        # Construct full path
        file_path = os.path.join(
            self.base_path,
            'query_results',
            str(query.user_id),
            str(query.query_id),
            filename
        )

        try:
            if os.path.exists(file_path):
                os.remove(file_path)

            logger.debug(f"Creating directory: {os.path.dirname(file_path)}")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(results.column_names)
                writer.writerows(results.rows)
        except Exception as e:
            logger.error(f"Error saving CSV: {e}", exc_info=True)
            raise  # Re-raise for Sentry to capture

        return file_path
    
    def get_download_path(self, save_path: str):
        download_path =  QueryToolBackend().service_url + QueryToolBackend().route + save_path
        return download_path