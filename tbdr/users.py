from flask import (
	Blueprint, flash, g, redirect, render_template, request, url_for, Response
)
from collections import Counter
from werkzeug.exceptions import abort
import json
import os.path
from flask import current_app as app
from flask_login import login_required, current_user
from .db import get_neo4j_db

bp = Blueprint('users', __name__)

def add_links(runs):
	for run in runs:
		run["link"] = "<a href='%s'>%s</a>" % (url_for('results.run_result',sample_id=run["id"]),run["sample_name"])
		run["status"] = "Processing" if "Processing" in run["labels"] else "Completed"
		run["timestamp"] = run["timestamp"].split(".")[0]
	return runs

@bp.route('/user/home',methods=('GET', 'POST'))
@login_required
def home():
	neodb = get_neo4j_db()
	data = neodb.read("MATCH (n:Private {userID:'%s'}) return n.id as id, n.timestamp as timestamp, n.drtype as drtype,n.subLineage as sublineage, n.sampleName as sample_name, labels(n) as labels" % current_user.id)
	runs = add_links(data)
		
	return render_template('user/user_home.html',runs = data)



@bp.route('/data_agreement')
def data_agreement():
	data_agreement_file = app.config["APP_ROOT"]+url_for('static', filename='data_agreement.txt')
	print(data_agreement_file)
	text = open(data_agreement_file).read().replace("\n","<br>") if os.path.isfile(data_agreement_file) else "No data agreement has been set yet!"
	return render_template('user/data_agreement.html',text=text)
