# tests/test_server.py
from lexios.lexios_server_init import LexiOS_Server

def test_run_celery_task():
    server = LexiOS_Server()
    server.run_celery_task()

# Add more tests as needed
