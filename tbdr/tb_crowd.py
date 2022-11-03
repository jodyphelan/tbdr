from flask import (
	Blueprint, flash, g, redirect, render_template, request, url_for, Response
)
from collections import Counter
from werkzeug.exceptions import abort
import json
import os.path
from flask import current_app as app
from flask_login import login_required, current_user
from .tb_crowd_forms import MetaForm
import csv 
import codecs 

bp = Blueprint('tb_crowd', __name__)

drugs = ["rifampicin","isoniazid","ethambutol","pyrazinamide"]

def add_links(runs):
	for run in runs:
		run["link"] = "<a href='%s'>%s</a>" % (url_for('results.run_result',sample_id=run["id"]),run["sample_name"])
		run["status"] = "Processing" if "Processing" in run["labels"] else "Completed"
		run["timestamp"] = run["timestamp"].split(".")[0]
	return runs

@bp.route('/tb-crowd/home',methods=('GET', 'POST'))
@login_required
def home():
    neodb = get_neo4j_db()
    drug_query = ", ".join(["n.%s as %s" %  (d.lower(), d) for d in drugs])
    data = neodb.read("MATCH (n:Private {userID:'%s'}) return n.id as id, n.timestamp as timestamp, n.drtype as drtype,n.subLineage as sublineage, n.sampleName as sample_name, labels(n) as labels, %s" % (current_user.id,drug_query))
    runs = add_links(data)
    form = MetaForm()
    if form.validate_on_submit():
        reader = csv.DictReader(codecs.iterdecode(form.file1.data.stream, 'utf-8'))
        if reader.fieldnames!=['Run ID']+drugs:
            flash("Error with CSV format")
            return render_template('tb_crowd/user_home.html',runs = data,form=form)
        for row in reader:
            for d in drugs:
                if row[d]=="R" or row[d]=="1":
                    print("Setting %s -> %s = %s" % (row["Run ID"],d,"R"))
                    neodb.write('MATCH (n:Private {id:"%s"}) SET n.%s="%s"' % (row["Run ID"],d,"R"))
                if row[d]=="S" or row[d]=="0":
                    print("Setting %s -> %s = %s" % (row["Run ID"],d,"S"))
                    neodb.write('MATCH (n:Private {id:"%s"}) SET n.%s="%s"' % (row["Run ID"],d,"S"))
    performance = {}
    for d in drugs:
        performance[d] = get_performance(d)
    return render_template('tb_crowd/user_home.html',runs = data,form=form,performance = performance)

def get_performance(drug):
    neodb = get_neo4j_db()

    data = {}
    tmp_data = neodb.read(f"match (n:Private {{userID:'{current_user.id}'}}) WHERE n.{drug} in ['R','S'] OPTIONAL MATCH (n)-->(v:Variant)-[:CONFERS_RESISTANCE]-> (:Drug {{id:'{drug}'}}) RETURN  n, count(v) as v")
    tab = [[0,0],[0,0]]
    times = []
    dst = []
    for i,row in enumerate(tmp_data):
        times.append(datetime.datetime.strptime(row["n"]["timestamp"],"%Y-%m-%dT%H:%M:%S.%f"))
        dst.append(row["n"][drug])
        if row["n"][drug]=="R" and row["v"]>0:
            tab[0][0]+=1
        elif row["n"][drug]=="S" and row["v"]>0:
            tab[0][1]+=1
        elif row["n"][drug]=="R" and row["v"]==0:
            tab[1][0]+=1
        elif row["n"][drug]=="S" and row["v"]==0:
            tab[1][1]+=1
    data["table"]=tab
    data["sensitivity"] = tab[0][0]/(tab[0][0] + tab[0][1])
    data["specificity"] = tab[1][1]/(tab[1][0] + tab[1][1])
    data["times"] = times
    data["dst"] = dst
    return data

import datetime
# import pandas as pd
# import plotly.express as px
import tbprofiler
conf = tbprofiler.get_conf_dict("tbdb")
drugs2lt = tbprofiler.get_drugs2lt("/home/jody/github/tbdb/tbdb.bed")
@bp.route('/tb-crowd/performance/<drug>')
@login_required
def drug_performance(drug):
    neodb = get_neo4j_db()
    data = get_performance(drug)
    
    data["fn_mutations"] = neodb.read(f"match (n:Private {{userID:'{current_user.id}'}}) WHERE (n.{drug}='R' AND  NOT (n)-->(:Variant)-->(:Drug {{id:'{drug}'}})) MATCH (n)-->(v:Variant) WHERE v.locus_tag in {str(drugs2lt[drug])} return v.gene as gene, v.locus_tag as locus_tag, v.change as change, count(n) as count")
    data["fp_mutations"] = neodb.read(f"match (n:Private {{userID:'{current_user.id}'}}) WHERE (n.{drug}='S' AND  (n)-->(:Variant)-->(:Drug {{id:'{drug}'}})) MATCH (n)-->(v:Variant)-->(d:Drug {{id:'{drug}'}})  return v.gene as gene, v.locus_tag as locus_tag, v.change as change, count(n) as count")
    for v in data["fn_mutations"]:
        v["link"] = "<a href='%s'>%s</a>" % (url_for('variants.variant',gene=v['locus_tag'],variant=v['change']),v["change"])
    for v in data["fp_mutations"]:
        v["link"] = "<a href='%s'>%s</a>" % (url_for('variants.variant',gene=v['locus_tag'],variant=v['change']),v["change"])
    df = pd.DataFrame(data={"timestamp":data["times"],"dst":data["dst"]})
    

    fig = px.histogram(df, x="timestamp", color="dst", marginal="rug",template="simple_white",nbins=10)
    data["figure"] = fig.to_html(full_html=False)
    data["drug"] = drug
    return render_template('tb_crowd/drug_performance.html',data=data)
    



@bp.route('/tb_crowd/get_template')
@login_required
def get_meta_template():
    neodb = get_neo4j_db()
    drug_query = ", ".join(["n.%s as %s" % (d.lower(), d) for d in drugs])
    data = neodb.read("MATCH (n:Private {userID:'%s'}) return n.id as id, n.timestamp as timestamp, n.sampleName as sample_name, %s" % (current_user.id,drug_query))
    
    csv_text = "Run ID,Name,Timestamp,%s\n" % ",".join(drugs)
    for row in data:
        csv_text = csv_text +  ",".join([row[x] if isinstance(row[x], str) else "" for x in ["id","sample_name","timestamp"]+drugs]) + "\n"
    return Response(csv_text,mimetype="text/csv",headers={"Content-disposition": "attachment; filename=tb-profiler-IDs.csv"})

@bp.route('/tb_crowd/submit_meta.csv',methods=('GET', 'POST'))
@login_required
def submit_meta_template():
    neodb = get_neo4j_db()
    data = neodb.read("MATCH (n:Private {userID:'%s'}) return n.id as id, n.timestamp as timestamp, n.sampleName as sample_name" % current_user.id)
    
    csv_text = "Run ID,Name,Timestamp,Bedaquiline,Delamanid\n" + "\n".join(["%(id)s,%(sample_name)s,%(timestamp)s,," % d for d in data])
    return Response(csv_text,mimetype="text/csv",headers={"Content-disposition": "attachment; filename=tb-profiler-IDs.csv"})


@bp.route('/data_agreement')
def data_agreement():
	data_agreement_file = app.config["APP_ROOT"]+url_for('static', filename='data_agreement.txt')
	print(data_agreement_file)
	text = open(data_agreement_file).read().replace("\n","<br>") if os.path.isfile(data_agreement_file) else "No data agreement has been set yet!"
	return render_template('tb_crowd/data_agreement.html',text=text)

