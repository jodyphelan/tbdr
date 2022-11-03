from glob import glob
import shutil
from celery import Celery
import subprocess as sp
import json
import pathogenprofiler as pp
import os
from flask import Flask
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

    bam_file = "%s/bam/%s.bam" % (result_file_dir,uniq_id)
    pp.run_cmd("samtools view -b -L %s %s > %s/%s.targets.bam" % (conf["bed"], bam_file, result_file_dir, uniq_id))
    pp.run_cmd("samtools index  %s/%s.targets.bam" % (result_file_dir, uniq_id))
    pp.run_cmd("bcftools view %s/vcf/%s.targets.csq.vcf.gz > %s/%s.targets.vcf" % (result_file_dir,uniq_id,result_file_dir,uniq_id))
    shutil.copyfile("%s/results/%s.results.json" % (result_file_dir,uniq_id),"%s/%s.results.json" % (result_file_dir,uniq_id))
    for d in ['bam','vcf','results']:
        for f in glob("%s/%s/*" % (result_file_dir,d)):
            os.remove(f)
    return True