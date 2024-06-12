cd bin
celery -A make_celery worker --loglevel=INFO --concurrency=1 --time-limit 3600

