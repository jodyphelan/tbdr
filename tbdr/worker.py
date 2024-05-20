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
from time import sleep
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

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

def get_drug_table(dr_variants,conf):
    all_drugs = conf['drugs']
    new_table = []
    for v in dr_variants:
        for d in v['drugs']:
            new_row = {
                'drug': d['drug'],
                'gene': v['gene_name'],
                'change': v['change'],
                'confidence': d['confidence'],
                'comment': d['comment'],
            }
            new_table.append(new_row)
    variant_drugs = list(set([r['drug'] for r in new_table]))
    for d in all_drugs:
        if d not in variant_drugs:
            new_table.append({
                'drug': d,
                'gene': '',
                'change': '',
                'confidence': '',
                'comment': '',
            })
    
    new_table = sorted(new_table, key=lambda x: all_drugs.index(x['drug']))
    for drug in all_drugs:
        drugrows = [d for d in new_table if d['drug'] == drug]
        for i,r in enumerate(drugrows):
            if i == 0:
                r['drug-rowspan'] = len(drugrows)
            generows = [g for g in drugrows if g['gene'] == r['gene']]
            for j,g in enumerate(generows):
                if j == 0:
                    g['gene-rowspan'] = len(generows)
    return new_table

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
    data['drug_table'] = get_drug_table(data['dr_variants'],conf)
    for var in data['other_variants']:
        var['grading'] = {a['drug']:a['confidence'] for a in var['annotation']}
    data['migrated'] = False
    logger.info("Finished run for %s" % uniq_id)
    logger.info("Starting DB entry for %s" % uniq_id)
    db_entry = Result.query.filter(Result.sample_id == uniq_id).first()
    db_entry.data = data
    db_entry.status = "Completed"
    db_session.commit()
    logger.info("Extracting bam file for %s" % uniq_id)
    bam_file = "%s/bam/%s.bam" % (result_file_dir,uniq_id)
    pp.run_cmd("samtools view -b -L %s %s > %s/%s.targets.bam" % (conf["bed"], bam_file, result_file_dir, uniq_id))
    logger.info("Indexing bam file for %s" % uniq_id)
    pp.run_cmd("samtools index  %s/%s.targets.bam" % (result_file_dir, uniq_id))
    logger.info("Extracting vcf file for %s" % uniq_id)
    pp.run_cmd("bcftools view %s/vcf/%s.targets.vcf.gz > %s/%s.targets.vcf" % (result_file_dir,uniq_id,result_file_dir,uniq_id))
    
    for f in glob("%s/results/%s*" % (result_file_dir,uniq_id)):
        logger.info("Copying %s file for %s" % (f,uniq_id))
        shutil.copyfile(f,"%s/%s" % (result_file_dir,f.split("/")[-1]))

    for d in ['bam','vcf','results']:
        for f in glob("%s/%s/%s*" % (result_file_dir,d,uniq_id)):
            logger.info("Removing %s file for %s" % (f,uniq_id))
            os.remove(f)
    
    os.remove(fq1)
    if fq2:
        os.remove(fq2)
    return True

def run_tb_profiler_command(fq1,fq2,uniq_id,platform,result_file_dir):
    platform = platform.lower()
    logger.info("Starting run for %s" % uniq_id)
    with open("%s/%s.log" % (result_file_dir,uniq_id), "a",buffering=1) as LOG:
        if fq1 and fq2:
            sp.call(f"tb-profiler profile --spoligotype --ram 8 --threads 2 --txt --csv -1 {fq1} -2 {fq2} -m {platform.lower()} -p {uniq_id} --dir {result_file_dir}",shell=True, stderr=LOG,stdout=LOG)
        else:
            sp.call(f"tb-profiler profile --spoligotype --ram 8 --threads 2 --txt --csv -1 {fq1} -m {platform.lower()} -p {uniq_id} --dir {result_file_dir}",shell=True, stderr=LOG,stdout=LOG)


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
    for var in data['other_variants']:
        var['grading'] = {a['drug']:a['confidence'] for a in var['drugs']}


    logger.info("Finished run for %s" % uniq_id)
    logger.info("Starting DB entry for %s" % uniq_id)
    db_entry = Result.query.filter(Result.sample_id == uniq_id).first()
    db_entry.data = data
    db_entry.status = "Completed"
    db_session.commit()
    logger.info("Extracting bam file for %s" % uniq_id)
    bam_file = f"{tmp_dir}/{uniq_id}.bam" 
    pp.run_cmd(f"samtools view -b -L {conf['bed']} {bam_file} > {result_file_dir}/{uniq_id}.targets.bam" )
    logger.info("Indexing bam file for %s" % uniq_id)
    pp.run_cmd("samtools index  %s/%s.targets.bam" % (result_file_dir, uniq_id))
    logger.info("Extracting vcf file for %s" % uniq_id)
    pp.run_cmd(f"bcftools view {tmp_dir}/{uniq_id}.targets.vcf.gz > {result_file_dir}/{uniq_id}.targets.vcf")
    
    for k,v in result_files.items():
        shutil.copyfile(f"{tmp_dir}/{v}",f"{result_file_dir}/{v}" )
        
    for f in glob(f"{tmp_dir}/{uniq_id}*"):
        logger.info("Copying %s file for %s" % (f,uniq_id))
        os.remove(f)
    
    os.remove(fq1)
    if fq2:
        os.remove(fq2)
    return True