"""Celery application entry point for workers and task inspection."""

from . import create_app

flask_app = create_app()
celery = flask_app.extensions["celery"]

# Import tasks after the Flask-configured Celery instance is the default app.
from . import worker  # noqa: E402,F401
