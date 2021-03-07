from flask import (
	Blueprint, flash, g, redirect, render_template, request, url_for, Response
)
from collections import Counter
from werkzeug.exceptions import abort
import json
from tbdr.auth import login_required
from tbdr.db import get_db
from tbdr.results import result_table
import os.path
import tbprofiler as tbp
from flask import current_app as app

bp = Blueprint('users', __name__)


@login_required
@bp.route('/user/results',methods=('GET', 'POST'))
def user_results():
	return result_table(request,g.user['username'])

@login_required
@bp.route('/user/home',methods=('GET', 'POST'))
def user_home():
	db = get_db()
	data = {}
	sql_query = "select id,sample_name,created,status,lineage,drtype from results WHERE user_id = '%s'" % g.user["username"]
	raw_data = db.execute(sql_query).fetchall()
	data["num_samples"] = len(raw_data)
	data["top_lineage"] = Counter([x["lineage"] for x in raw_data]).most_common(1)[0][0]
	data["top_drtype"] = Counter([x["drtype"] for x in raw_data]).most_common(1)[0][0]
	return render_template('user/user_home.html',data=data)


@bp.route('/data_agreement')
def data_agreement():
	data_agreement_file = app.config["APP_ROOT"]+url_for('static', filename='data_agreement.txt')
	print(data_agreement_file)
	text = open(data_agreement_file).read().replace("\n","<br>") if os.path.isfile(data_agreement_file) else "No data agreement has been set yet!"
	return render_template('user/data_agreement.html',text=text)
