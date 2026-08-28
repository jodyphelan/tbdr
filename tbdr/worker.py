from glob import glob
import shutil
from celery import Celery, Task
import subprocess as sp
import json
import pathogenprofiler as pp
import os
from flask import Flask
from time import sleep
from celery.utils.log import get_task_logger
from .models import Result, add_sample_to_db
from .db import db_session
from celery import shared_task
import sys

from tbdr import create_app



logger = get_task_logger(__name__)


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


@shared_task
def tbprofiler(fq1,fq2,uniq_id,upload_dir,platform,result_file_dir):
    from flask import current_app

    db_dir = current_app.config['TB_PROFILER_DB_DIR']
    db_name = current_app.config['TB_PROFILER_DB']
    is_public = current_app.config['SAMPLES_PUBLIC']
    db_entry = Result.query.filter(Result.sample_id == uniq_id).first()
    try:
        run_tb_profiler_command(fq1, fq2, uniq_id, platform, result_file_dir)
        with open("%s/results/%s.results.json" % (result_file_dir, uniq_id)) as result_handle:
            data = json.load(result_handle)
        conf = pp.get_db(db_dir, db_name)
        data['drug_table'] = get_drug_table(data['dr_variants'], conf)
        for var in data['other_variants']:
            var['grading'] = {a['drug']: a['confidence'] for a in var['annotation']}
        data['migrated'] = False
        logger.info("Finished run for %s", uniq_id)
        logger.info("Starting DB entry for %s", uniq_id)
        db_entry.data = data
        db_entry.status = "Completed"
        db_session.commit()
        logger.info("Extracting bam file for %s", uniq_id)
        bam_file = "%s/bam/%s.bam" % (result_file_dir, uniq_id)
        target_bam = "%s/%s.targets.bam" % (result_file_dir, uniq_id)
        sp.run(
            ['samtools', 'view', '-b', '-L', conf['bed'], bam_file, '-o', target_bam],
            check=True,
        )
        logger.info("Indexing bam file for %s", uniq_id)
        sp.run(['samtools', 'index', target_bam], check=True)
        logger.info("Extracting vcf file for %s", uniq_id)
        sp.run([
            'bcftools', 'view', "%s/vcf/%s.vcf.gz" % (result_file_dir, uniq_id),
            '-o', "%s/%s.vcf" % (result_file_dir, uniq_id),
        ], check=True)

        for result_path in glob("%s/results/%s*" % (result_file_dir, uniq_id)):
            logger.info("Copying %s file for %s", result_path, uniq_id)
            shutil.copyfile(result_path, "%s/%s" % (result_file_dir, result_path.split('/')[-1]))

        for directory in ['bam', 'vcf', 'results']:
            for result_path in glob("%s/%s/%s*" % (result_file_dir, directory, uniq_id)):
                logger.info("Removing %s file for %s", result_path, uniq_id)
                os.remove(result_path)

        os.remove(fq1)
        if fq2:
            os.remove(fq2)
        if is_public:
            add_sample_to_db(uniq_id, {"iso_a3": "IRL", "country": "Ireland", "year_of_collection": 2024})
        
        return True
    except Exception:
        logger.exception("TB-Profiler failed for %s", uniq_id)
        if db_entry:
            db_entry.status = "Failed"
            db_session.commit()
        raise

def run_tb_profiler_command(fq1,fq2,uniq_id,platform,result_file_dir):
    from flask import current_app

    platform = platform.lower()
    logger.info("Starting run for %s" % uniq_id)
    with open("%s/%s.log" % (result_file_dir,uniq_id), "a",buffering=1) as LOG:
        command = [
            'tb-profiler', 'profile', '--ram', str(current_app.config['TB_PROFILER_RAM_GB']),
            '--threads', str(current_app.config['TB_PROFILER_THREADS']), '--txt', '--csv',
            '--db', current_app.config['TB_PROFILER_DB'],
            '--db_dir', current_app.config['TB_PROFILER_DB_DIR'], '-1', fq1,
            '-m', platform, '-p', uniq_id, '--dir', result_file_dir,
        ]
        if fq1 and fq2:
            command[command.index('-1'):command.index('-1')] = ['-2', fq2]
        else:
            if platform == "nanopore":
                command.extend(['--caller', 'bcftools'])
        sp.run(command, check=True, stderr=LOG, stdout=LOG)
