"""A webserver interface for the TB-Profiler"""

__version__ = "2.0.0"


import os
from flask import Flask
from . import db
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import redis
from flask_session import Session



sqldb = SQLAlchemy()
login_manager = LoginManager()
sess = Session()

def create_app(test_config=None):
	# create and configure the app
	app = Flask(__name__, instance_relative_config=True)
	app.config.from_mapping(
		SECRET_KEY='dev',
		UPLOAD_FOLDER="/tmp",
		APP_ROOT=os.path.dirname(os.path.abspath(__file__)),
		
		
		SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://@localhost/tbdr",
    	SQLALCHEMY_ECHO = False,
    	SQLALCHEMY_TRACK_MODIFICATIONS = False,

		SESSION_TYPE = "redis",
    	SESSION_REDIS = redis.from_url("redis://localhost:6379")
	)

	sqldb.init_app(app)
	login_manager.init_app(app)
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

		# Create Database Models
		sqldb.create_all()

		from .db import db_session
		@app.teardown_appcontext
		def shutdown_session(exception=None):
			db_session.remove()

		return app
