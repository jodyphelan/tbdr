from celery import Celery
import subprocess as sp
import json
import sqlite3
import pathogenprofiler as pp
import tbprofiler as tbp
import os
import sys
from flask import Flask,current_app,url_for
# import statsmodels.api as sm
# import numpy as np
from datetime import datetime
from .models import Result
from .db import db_session

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery



flask_app = Flask(__name__)
flask_app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379',
    CELERY_RESULT_BACKEND='redis://localhost:6379',
)
celery = make_celery(flask_app)

@celery.task
def tbprofiler(fq1,fq2,uniq_id,upload_dir,platform,result_file_dir):

    with open("%s/%s.log" % (result_file_dir,uniq_id), "a",buffering=1) as LOG:
        if fq1 and fq2:
            sp.call(f"tb-profiler profile --threads 2 -1 {fq1} -2 {fq2} -m {platform.lower()} -p {uniq_id} --dir {result_file_dir}",shell=True)
    data = json.load(open("%s/results/%s.results.json" % (result_file_dir,uniq_id)))
    conf = pp.get_db('tbprofiler','tbdb')
    data = pp.get_summary(data,conf)

    db_entry = Result.query.filter(Result.sample_id == uniq_id).first()
    db_entry.data = data
    db_entry.status = "Completed"
    db_session.commit()

    return True



@celery.task
def calculate_mutation_stats(gene,variant,pval_cutoff=0.05):
    with flask_app.app_context():
        neo4j_db = get_neo4j_db()

        conf = tbp.get_conf_dict("tbdb")
        lt2drugs = tbp.get_lt2drugs(conf["bed"])
        json_db = json.load(open(conf["json_db"]))


        if gene in json_db and variant in json_db[gene]:
            drugs = list(json_db[gene][variant])
        else:
            drugs = lt2drugs[gene]


        results = []
        for drug in drugs:
            if drug=="para-aminosalicylic_acid": drug = "paraAminosalicylicAcid"
            num_tested = neo4j_db.read("MATCH (s:Sample) WHERE s.%s<>'NA' return s.%s as dst, count(*) as count" % (drug,drug))
            num_tested = {list(x.values())[0]:list(x.values())[1] for x in num_tested }

            variant_data = neo4j_db.read("MATCH (v:Variant {id:'%s_%s'}) <-[:CONTAINS]- (s:Sample) return s.%s as dst, count(*) as count" % (gene,variant,drug))
            variant_data = {list(x.values())[0]:list(x.values())[1] for x in variant_data}
            t = [
                    [0.5, 0.5],
                    [0.5, 0.5]
                ]

            t[0][0] = variant_data.get("1",0.5)
            t[0][1] = variant_data.get("0",0.5)
            t[1][0] = num_tested.get("1",0.5) - variant_data.get("1",0)
            t[1][1] = num_tested.get("0",0.5) - variant_data.get("0",0)

            t2 = sm.stats.Table2x2(np.asarray(t))

            result = {"drug":drug}
            result["odds ratio"] = t2.oddsratio if t[0]!=[0.5,0.5] else "NA"
            result["odds ratio p-value"] = t2.oddsratio_pvalue() if t[0]!=[0.5,0.5] else "NA"
            result["risk ratio"] = t2.riskratio if t[0]!=[0.5,0.5] else "NA"
            result["risk ratio p-value"] = t2.riskratio_pvalue() if t[0]!=[0.5,0.5] else "NA"

            if result["odds ratio"]=="NA":
                result["confidence"] = "indeterminate"
            elif result["odds ratio"]>10 and result["odds ratio p-value"]<pval_cutoff and result["risk ratio"]>1 and result["risk ratio p-value"]<pval_cutoff:
                result["confidence"] = "high"
            elif 5<result["odds ratio"]<=10 and result["odds ratio p-value"]<pval_cutoff and result["risk ratio"]>1 and result["risk ratio p-value"]<pval_cutoff:
                result["confidence"] = "moderate"
            elif 1<result["odds ratio"]<=5 and result["odds ratio p-value"]<pval_cutoff and result["risk ratio"]>1 and result["risk ratio p-value"]<pval_cutoff:
                result["confidence"] = "low"
            elif (result["odds ratio"]<=1 and result["odds ratio p-value"]<pval_cutoff) or (result["risk ratio"]<=1 and result["risk ratio p-value"]<pval_cutoff):
                result["confidence"] = "no_association"
            else:
                result["confidence"] = "indeterminate"

            results.append(result)

        neo4j_db.write(
            "MERGE (v:Variant {id:'%s_%s'})" % (gene,variant),
            "SET v.support = '%s'" % json.dumps(results)
        )
