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
    run_tb_profiler_command(fq1,fq2,uniq_id,platform,result_file_dir)
    data = json.load(open("%s/results/%s.results.json" % (result_file_dir,uniq_id)))
    conf = pp.get_db('tbprofiler','tbdb')
    data = pp.get_summary(data,conf)

    pp.debug("Finished run for %s" % uniq_id)
    pp.debug("Starting DB entry for %s" % uniq_id)
    db_entry = Result.query.filter(Result.sample_id == uniq_id).first()
    db_entry.data = data
    db_entry.status = "Completed"
    db_session.commit()
    pp.debug("Extracting bam file for %s" % uniq_id)
    bam_file = "%s/bam/%s.bam" % (result_file_dir,uniq_id)
    pp.run_cmd("samtools view -b -L %s %s > %s/%s.targets.bam" % (conf["bed"], bam_file, result_file_dir, uniq_id))
    pp.debug("Indexing bam file for %s" % uniq_id)
    pp.run_cmd("samtools index  %s/%s.targets.bam" % (result_file_dir, uniq_id))
    pp.debug("Extracting vcf file for %s" % uniq_id)
    pp.run_cmd("bcftools view %s/vcf/%s.targets.csq.vcf.gz > %s/%s.targets.vcf" % (result_file_dir,uniq_id,result_file_dir,uniq_id))
    
    for f in glob("%s/results/%s*" % (result_file_dir,uniq_id)):
        pp.debug("Copying %s file for %s" % (f,uniq_id))
        shutil.copyfile(f,"%s/%s" % (result_file_dir,f.split("/")[-1]))

    for d in ['bam','vcf','results']:
        for f in glob("%s/%s/%s*" % (result_file_dir,d,uniq_id)):
            pp.debug("Removing %s file for %s" % (f,uniq_id))
            os.remove(f)
    
    os.remove(fq1)
    if fq2:
        os.remove(fq2)
    return True

def run_tb_profiler_command(fq1,fq2,uniq_id,platform,result_file_dir):
    platform = platform.lower()
    pp.debug("Starting run for %s" % uniq_id)
    with open("%s/%s.log" % (result_file_dir,uniq_id), "a",buffering=1) as LOG:
        if fq1 and fq2:
            sp.call(f"tb-profiler profile --spoligotype --ram 8 --threads 2 --txt --csv --pdf -1 {fq1} -2 {fq2} -m {platform.lower()} -p {uniq_id} --dir {result_file_dir}",shell=True, stderr=LOG,stdout=LOG)
        else:
            sp.call(f"tb-profiler profile --spoligotype --ram 8 --threads 2 --txt --csv --pdf -1 {fq1} -m {platform.lower()} -p {uniq_id} --dir {result_file_dir}",shell=True, stderr=LOG,stdout=LOG)


def profile_remote(fq1,fq2,uniq_id,upload_dir,platform,result_file_dir):
    tmp_dir = f"/tmp/runs/"
    conf = {
        "platform": platform,
        "read1": fq1,
        "read2": fq2 if fq2 else None
    }
    json.dump(open(f"/tmp/runs/{uniq_id}.json"))
    completion_json = f"/tmp/runs/{uniq_id}.completed.json"
    while True:
        sleep(1)
        if os.path.exists(completion_json):
            break
    result_files = json.load(open(completion_json))
    
    data = json.load(open(f"{tmp_dir}/{uniq_id}.results.json"))
    conf = pp.get_db('tbprofiler','tbdb')
    data = pp.get_summary(data,conf)

    pp.debug("Finished run for %s" % uniq_id)
    pp.debug("Starting DB entry for %s" % uniq_id)
    db_entry = Result.query.filter(Result.sample_id == uniq_id).first()
    db_entry.data = data
    db_entry.status = "Completed"
    db_session.commit()
    pp.debug("Extracting bam file for %s" % uniq_id)
    bam_file = f"{tmp_dir}/{uniq_id}.bam" 
    pp.run_cmd(f"samtools view -b -L {conf['bed']} {bam_file} > {result_file_dir}/{uniq_id}.targets.bam" )
    pp.debug("Indexing bam file for %s" % uniq_id)
    pp.run_cmd("samtools index  %s/%s.targets.bam" % (result_file_dir, uniq_id))
    pp.debug("Extracting vcf file for %s" % uniq_id)
    pp.run_cmd(f"bcftools view {tmp_dir}/{uniq_id}.targets.csq.vcf.gz > {result_file_dir}/{uniq_id}.targets.vcf")
    
    for k,v in result_files.items():
        shutil.copyfile(f"{tmp_dir}/{v}",f"{result_file_dir}/{v}" )
        
    for f in glob(f"{tmp_dir}/{uniq_id}*"):
        pp.debug("Copying %s file for %s" % (f,uniq_id))
        os.remove(f)
    
    os.remove(fq1)
    if fq2:
        os.remove(fq2)
    return True