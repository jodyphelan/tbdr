cd bin
celery -A make_celery worker --loglevel=INFO --concurrency=1

