"""A webserver interface for the TB-Profiler"""

__version__ = "2.0.0"


import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
# from flask_login import LoginManager
import redis
from flask_session import Session
from sqlalchemy import text
from sqlalchemy.engine import URL


from celery import Celery, Task

def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app



sqldb = SQLAlchemy()
# login_manager = LoginManager()
sess = Session()

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('TBDR_SECRET_KEY', 'dev'),
        UPLOAD_FOLDER=os.environ.get('TBDR_UPLOAD_DIR', '/tmp'),
        APP_ROOT=os.path.dirname(os.path.abspath(__file__)),
        RESULTS_FOLDER=os.environ.get(
            'TBDR_RESULTS_DIR',
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'results'),
        ),
        TB_PROFILER_DB=os.environ.get('TBDR_TBPROFILER_DB', 'who_v3'),
        TB_PROFILER_DB_DIR=os.environ.get(
            'TBDR_TBPROFILER_DB_DIR',
            os.path.join(getattr(sys, 'base_prefix', sys.prefix), 'share', 'tbprofiler'),
        ),
        TB_PROFILER_THREADS=int(os.environ.get('TBDR_PROFILE_THREADS', '2')),
        TB_PROFILER_RAM_GB=int(os.environ.get('TBDR_PROFILE_RAM_GB', '8')),
        
        
        SQLALCHEMY_ECHO = False,
        SQLALCHEMY_TRACK_MODIFICATIONS = False,

        SESSION_TYPE="redis",
    )
    settings_path = os.environ.get('YOURAPPLICATION_SETTINGS')
    if settings_path:
        app.config.from_envvar('YOURAPPLICATION_SETTINGS', silent=False)

    redis_url = os.environ.get('TBDR_REDIS_URL', 'redis://localhost:6379/0')
    app.config['SESSION_REDIS'] = redis.from_url(redis_url)

    db_user = os.environ.get('POSTGRES_USER', app.config.get('PG_USER', 'tbdr'))
    db_password = os.environ.get('POSTGRES_PASSWORD', app.config.get('PG_PASS', 'tbdr'))
    db_name = os.environ.get('POSTGRES_DB', app.config.get('PG_DB', 'tbdr'))
    db_host = os.environ.get('TBDR_DB_HOST', app.config.get('PG_HOST', 'localhost'))
    db_port = int(os.environ.get('TBDR_DB_PORT', app.config.get('PG_PORT', '5432')))
    app.config.update(PG_USER=db_user, PG_PASS=db_password, PG_DB=db_name,
                      PG_HOST=db_host, PG_PORT=db_port)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'TBDR_DATABASE_URL',
        URL.create(
            'postgresql+psycopg2',
            username=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            database=db_name,
        ).render_as_string(hide_password=False),
    )

    broker_url = os.environ.get('TBDR_CELERY_BROKER_URL', redis_url)
    result_backend = os.environ.get('TBDR_CELERY_RESULT_BACKEND', redis_url)
    app.config.from_mapping(
          CELERY=dict(
              broker_url=broker_url,
              result_backend=result_backend,
          ),
    )

    celery_init_app(app)

    sqldb.init_app(app)
    # login_manager.init_app(app)
    sess.init_app(app)
    
    with app.app_context():
        # from . import auth
        # app.register_blueprint(auth.bp)

        from . import home
        app.register_blueprint(home.bp)

        from . import results
        app.register_blueprint(results.bp)

        from . import upload
        app.register_blueprint(upload.bp)

        # from . import users
        # app.register_blueprint(users.bp)

        from . import variants
        app.register_blueprint(variants.bp)

        from . import sra
        app.register_blueprint(sra.bp)


        # from . import tb_crowd
        # app.register_blueprint(tb_crowd.bp)

        from .db import db_session
        @app.teardown_appcontext
        def shutdown_session(exception=None):
            db_session.remove()

        @app.get('/healthz')
        def healthz():
            db_session.execute(text('SELECT 1'))
            app.config['SESSION_REDIS'].ping()
            return {'status': 'ok'}

        return app
