"""
Script to insert results into the database.
"""
import argparse
import csv
import json
import os
from pathogenprofiler import pp
import sys
from tbdr import create_app
from tbdr.db import get_db_session
from tbdr.models import update_sample_data

app = create_app()



parser = argparse.ArgumentParser(description='tbprofiler script',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--json',type=str,help='File with samples',required = True)
parser.add_argument('--metadata-csv', type=str, help='Metadata CSV file', required=True)
parser.add_argument('--db', default="who_v3", type=str, help='Database name')

args = parser.parse_args()


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
    new_table = [r for r in new_table if r['drug'] in all_drugs]
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


db_dir = os.path.join(sys.base_prefix, 'share', 'tbprofiler')
conf = pp.get_db(db_dir,args.db)

    
data = json.load(open(args.json))
data['drug_table'] = get_drug_table(data['dr_variants'],conf=conf)
for var in data['other_variants']:
    var['grading'] = {a['drug']:a['confidence'] for a in var['annotation']}
sample_id = data['id']
meta = {'sample_name': sample_id}
if args.metadata_csv:
    for row in csv.DictReader(open(args.metadata_csv, encoding="utf-8-sig")):
        if row['wgs_id']==sample_id:
            meta = row
            break


with app.app_context():
    from tbdr.models import update_sample_data, Sample, Result
    db_session = get_db_session()

    # if existing sample or result, update them
    existing_result = Result.query.filter(Result.sample_id == sample_id).first()
    existing_sample = Sample.query.filter(Sample.id == sample_id).first()
    if existing_result:
        existing_result.data = data
        existing_result.status = 'completed'
        result = existing_result
    else:
        result = Result(sample_id=sample_id, data=data, status='completed')
    if existing_sample:
        for key, value in meta.items():
            setattr(existing_sample, key, value)
        sample = existing_sample
    else:
        sample = Sample(id=sample_id, **meta)




    db_session.add(result)
    db_session.commit()

    collections = []
    if args.public:
        collections.append('public')
    update_sample_data(sample_id, collections=collections)
    
    
