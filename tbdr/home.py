import os
from flask import (
	Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
import json
#from aseantb.auth import login_required
from flask import current_app as app
from flask_login import current_user, login_required

bp = Blueprint('home', __name__)


@bp.route('/',methods=('GET', 'POST'))
def index():
	print(vars(current_user))
	if request.method == 'POST':
		return redirect(url_for('results.run_result', sample_id=request.form["sample_id"]))
	return render_template('home/index.html')

@bp.route('/robots.txt')
def robots():
	return open(app.config["APP_ROOT"]+url_for('static',filename='robots.txt')).read().replace("\n","<br>")


@bp.route('/test')
@login_required
def test():
	return "hello" + current_user.name


from flask import send_from_directory

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')