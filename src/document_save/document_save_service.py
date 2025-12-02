import csv
import os
from config import FileRepo, QueryToolBackend
from src.queries.dto.execute_query_dto import ExecuteQueryDTO
from src.document_save.filename_service import FilenameService
from datetime import datetime

class DocumentSaveService:
    base_path = FileRepo.base_drive
    def save_to_csv(self, results, query:ExecuteQueryDTO):
        """Save query results with improved filename format."""
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

            print(os.path.dirname(file_path))
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(results.column_names)
                writer.writerows(results.rows)
        except Exception as e:
            print(f"Error saving CSV: {e}")
            raise  # Re-raise for Sentry to capture

        return file_path
    
    def get_download_path(self, save_path: str):
        download_path =  QueryToolBackend().service_url + QueryToolBackend().route + save_path
        return download_path