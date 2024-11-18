import os
import sys

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))
os.environ.update({'ROOT_PATH': ROOT_PATH})
sys.path.append(os.path.join(ROOT_PATH, 'src'))

from src.queries.query_service import QueryService

if __name__ == '__main__':
    QueryService().delete_expired_pending_applications()