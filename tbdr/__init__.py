import os
from flask import Flask
from . import db


def create_app(test_config=None):
	# create and configure the app
	app = Flask(__name__, instance_relative_config=True)
	app.config.from_mapping(
		SECRET_KEY='dev',
		UPLOAD_FOLDER="/tmp",
		APP_ROOT=os.path.dirname(os.path.abspath(__file__)),
		NEO4J_URI="neo4j://localhost:7687", NEO4J_USER="neo4j",
		NEO4J_PASSWORD="test",
	)

	if test_config is None:
		# load the instance config, if it exists, when not testing
		app.config.from_pyfile('config.py', silent=True)
	else:
		# load the test config if passed in
		app.config.from_mapping(test_config)



	from . import home
	app.register_blueprint(home.bp)

	from . import results
	app.register_blueprint(results.bp)

	from . import upload
	app.register_blueprint(upload.bp)

	# from . import auth
	# app.register_blueprint(auth.bp)

	# from . import users
	# app.register_blueprint(users.bp)

	from . import variants
	app.register_blueprint(variants.bp)

	from . import sra
	app.register_blueprint(sra.bp)

	return app
