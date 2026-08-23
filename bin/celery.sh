cd "$(dirname "$0")/.."
celery -A tbdr.celery_app:celery worker --loglevel=INFO --concurrency=1 --time-limit 3600
