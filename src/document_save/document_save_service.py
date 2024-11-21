import csv
import os
from config import FileRepo
from src.queries.dto.execute_query_dto import ExecuteQueryDTO

class DocumentSaveService:
    base_path = FileRepo.base_drive
    def save_to_csv(self, results, query:ExecuteQueryDTO):
        file_path = os.path.join(self.base_path,'query_results',str(query.user_id), str(query.query_id), f"{query.user_id} -{query.name}.csv")
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            print(os.path.dirname(file_path))
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerows(results.rows)
        except Exception as e:
            print(e)
        return file_path