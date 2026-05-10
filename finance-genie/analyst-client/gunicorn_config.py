import os


bind = f"0.0.0.0:{os.getenv('DATABRICKS_APP_PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
