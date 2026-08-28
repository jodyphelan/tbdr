from flask import (
	Blueprint, flash, g, redirect, render_template, request, url_for, Response
)
from werkzeug.exceptions import abort
import json
# from tbdr.auth import login_required
import tbprofiler as tbp
from flask import current_app as app
bp = Blueprint('results', __name__)
import os
from .db import db_session

from .models import Result

def get_result(sample_id):
	row =  Result.query.filter(Result.sample_id == sample_id).first()
	if row:
		return row	

	return None

@bp.route('/results/json/<sample_id>',methods=('GET', 'POST'))
def run_result_json(sample_id):
	results = get_result(sample_id)
	if results==None:
		return {"status":"Invalid_ID","result":None}
	if results["status"]!="Completed":
		log_file = app.config["APP_ROOT"]+url_for('static', filename='results/') + sample_id + ".log"
		progress = check_progress(log_file)
		return {"status":progress,"result":None}
	for var in results["dr_variants"]:
		var["drugs"] = ", ".join([d["id"] for d in var["drugs"]])

	return {"status":"OK","result":results}



@bp.route('/results/<sample_id>',methods=('GET', 'POST'))
def run_result(sample_id):
	result = get_result(sample_id)
	if result==None:
		flash("Error! Result with ID:%s doesn't exist" % sample_id)
		return redirect(url_for('home.index'))
	
	# print(result.data['migrated'])
	if sample_id[:3] not in ("DRR","SRR","ERR","SAM") and result.status!="Completed":
		log_file = app.config["APP_ROOT"]+url_for('static', filename='results/') + sample_id + ".log"
		progress = check_progress(log_file)
		log_text = open(log_file).read().replace(app.config["UPLOAD_FOLDER"]+"/","") if os.path.isfile(log_file) else ""
		return render_template('results/run_result.html',result = None,sample_id=sample_id,progress = progress,log_text=log_text)
	

	if request.method == 'POST':
		csv_strings = tbp.get_csv_strings(result,tbp.get_conf_dict("who_v2+"))
		csv_text = tbp.load_csv(csv_strings)
		return Response(csv_text,mimetype="text/csv",headers={"Content-disposition": "attachment; filename=%s.csv" % sample_id})


	bam_found = os.path.isfile(app.config["APP_ROOT"]+url_for('static', filename='results/') + sample_id + ".targets.bam")

	result.data['non_associated_variants_table'] = []
	for var in result.data['other_variants']:
		for drug,confidence in var['grading'].items():
		
			row = var.copy()
			row['change'] = '<a href="%s">%s</a>' % (url_for('variants.variant',gene=row['locus_tag'],variant=row['change']),row['change'])
			row['drug'] = drug
			row['confidence'] = confidence
			result.data['non_associated_variants_table'].append(row)

	result.data['associated_variants_table'] = []
	for var in result.data['dr_variants']:
		for ann in var['drugs']:

			row = var.copy()
			row['change'] = '<a href="%s">%s</a>' % (url_for('variants.variant',gene=row['locus_tag'],variant=row['change']),row['change'])
			row['drug'] = ann['drug']
			row['confidence'] = ann['confidence']
			row['comment'] = ann['comment']
			result.data['associated_variants_table'].append(row)
	return render_template('results/run_result.html',result = result.data, bam_found = bam_found, sample_id=sample_id)


def check_progress(filename):
	progress = "Uploaded"
	if not os.path.isfile(filename):
		progress = "In queue"
		return progress
	text = open(filename).read()
	if "Mapping to reference genome" in text:
		progress = "Mapping"
	if "Running variant calling" in text:
		progress = "Variant calling"
	if "Counting kmers" in text:
		progress = "Spoligotyping"
	if "Calculating bamstats" in text:
		progress = "Coverage analysis"
	if "Profiling complete!" in text:
		progress = "Completed"
	return progress

@bp.route('/results/progress/<result_id>',methods=('GET', 'POST'))
def get_progress(result_id):
	log_file = app.config["APP_ROOT"]+url_for('static', filename='results/') + result_id + ".log"
	progress = check_progress(log_file)
	return progress

def _get_log(result_id: str):
	log_file = app.config["APP_ROOT"]+url_for('static', filename='results/') + result_id + ".log"
	if not os.path.isfile(log_file):
		return "Log file not found"
	text = open(log_file).read().replace(app.config["UPLOAD_FOLDER"]+"/","") if os.path.isfile(log_file) else ""
	return text

@bp.route('/results/log/<result_id>',methods=('GET', 'POST'))
def get_log(result_id):
	log_text = _get_log(result_id)
	return log_text