from flask import (
	Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
import json
#from aseantb.auth import login_required
from tbdr.db import get_neo4j_db
from flask import current_app as app

bp = Blueprint('home', __name__)


@bp.route('/',methods=('GET', 'POST'))
def index():
	# neo4j = get_neo4j_db()
	if request.method == 'POST':
		return redirect(url_for('results.run_result', sample_id=request.form["sample_id"]))
	return render_template('home/index.html')

@bp.route('/robots.txt')
def robots():
	# neo4j = get_neo4j_db()
	return open(app.config["APP_ROOT"]+url_for('static',filename='robots.txt')).read().replace("\n","<br>")
