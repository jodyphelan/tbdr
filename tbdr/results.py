from flask import (
	Blueprint, flash, g, redirect, render_template, request, url_for, Response
)
from werkzeug.exceptions import abort
import json
# from tbdr.auth import login_required
from tbdr.db import  get_neo4j_db, read_neo4j_results
import tbprofiler as tbp
from flask import current_app as app
bp = Blueprint('results', __name__)
import os

def get_result(sample_id):
	sample_id = str(sample_id)
	neo4j_db = get_neo4j_db()
	tmp =  neo4j_db.read("MATCH (s:Sample {id:'%s'}) RETURN s" % sample_id)
	if tmp==[]:
		return None
	labels = list(set(tmp[0]["s"].labels))
	if "Processing" in labels:
		return {"id":sample_id,"labels":labels}
	results = read_neo4j_results(sample_id,neo4j_db,summary=True,conf = tbp.get_conf_dict("tbdb"))
	results["labels"] = labels
	return results

@bp.route('/results/json/<sample_id>',methods=('GET', 'POST'))
def run_result_json(sample_id):
	results = get_result(sample_id)
	if results==None:
		return {"status":"Invalid_ID","result":None}
	if "Processing" in results["labels"]:
		log_file = app.config["APP_ROOT"]+url_for('static', filename='results/') + sample_id + ".log"
		progress = check_progress(log_file)
		return {"status":progress,"result":None}
	for var in results["dr_variants"]:
		var["drugs"] = ", ".join([d["id"] for d in var["drugs"]])

	return {"status":"OK","result":results}



@bp.route('/results/<sample_id>',methods=('GET', 'POST'))
def run_result(sample_id):
	results = get_result(sample_id)
	if results==None:
		flash("Error! Result with ID:%s doesn't exist" % sample_id)
		return redirect(url_for('home.index'))
	print(results["labels"])
	if "Processing" in results["labels"]:
		log_file = app.config["APP_ROOT"]+url_for('static', filename='results/') + sample_id + ".log"
		progress = check_progress(log_file)
		
		log_text = open(log_file).read().replace(app.config["UPLOAD_FOLDER"]+"/","") if os.path.isfile(log_file) else ""
		return render_template('results/run_result.html',result = None,sample_id=sample_id,progress = progress,log_text=log_text)
	for var in results["dr_variants"]:
		var["drugs"] = ", ".join([d["id"] for d in var["drugs"]])

	if request.method == 'POST':
		csv_strings = tbp.get_csv_strings(results,tbp.get_conf_dict("tbdb"))
		csv_text = tbp.load_csv(csv_strings)
		return Response(csv_text,mimetype="text/csv",headers={"Content-disposition": "attachment; filename=%s.csv" % sample_id})


	bam_found = os.path.isfile(app.config["APP_ROOT"]+url_for('static', filename='results/') + sample_id + ".targets.bam")
	return render_template('results/run_result.html',result = results, bam_found = bam_found, sample_id=sample_id)


def check_progress(filename):
	progress = "Uploaded"
	if not os.path.isfile(filename):
		progress = "In queue"
		return progress
	text = open(filename).read()
	if "bwa mem" in text:
		progress = "Mapping"
	if "samtools fixmate"  in text:
		progress = "Bam sorting"
	if "samclip" in text:
		progress = "Variant calling"
	if "bcftools csq" in text:
		progress = "Variant annotation"
	if "%CHROM\\t%POS\\t%REF\\t%ALT[\\t%GT\\t%AD]" in text:
		progress = "Lineage determination"
	if "Profiling complete!" in text:
		progress = "Completed"
	return progress
