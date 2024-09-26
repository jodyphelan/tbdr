#! /usr/bin/env python

# Load useful libraries
import json
import argparse
import csv
from copy import copy
import sys
import pathogenprofiler as pp
import tbdr
import ena_query.query as eq


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


def main(args):
    from sqlalchemy import create_engine
    engine = create_engine(f"postgresql+psycopg2://{args.db_user}:{args.db_pass}@localhost/tbdr", echo=False)
    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy import select
    from sqlalchemy import MetaData
    from sqlalchemy import Table
    metadata_obj = MetaData()
    samples_table = Table("samples", metadata_obj, autoload_with=engine)
    results_table = Table("results", metadata_obj, autoload_with=engine)
    variant_table = Table("variants", metadata_obj, autoload_with=engine)
    sample_variants_table = Table("sample_variants", metadata_obj, autoload_with=engine)

    def add_sample(data):
        with engine.connect() as conn:
            if conn.execute(select(samples_table).where(samples_table.c.id == data["id"])).fetchone() != None:
                # remove existing results
                print("Removing existing results")
                conn.execute(results_table.delete().where(results_table.c.sample_id == data["id"]))
                conn.execute(sample_variants_table.delete().where(sample_variants_table.c.sample_id == data["id"]))
                conn.execute(samples_table.delete().where(samples_table.c.id == data["id"]))
                # conn.execute(variant_table.delete().where(variant_table.c.sample_id == data["id"]))
                conn.commit()


            json_data = copy(data)
            data['lineage'] = data['sub_lineage']
            sample_id = data['id']
            result = conn.execute(insert(samples_table),data)
            conn.commit()
            stmt = insert(results_table).values(data=json_data,sample_id=sample_id,status="Completed")
            result = conn.execute(stmt)
            conn.commit()
            rows = [
                {
                    'id': "%(locus_tag)s_%(change)s" % var,
                    'gene':var['gene_name'],
                    'change':var['change'],
                    'type':var['type'],
                    'locus_tag':var['locus_tag'],
                    'drugs': ", ".join([d['drug'] for d in var['drugs']]) if 'drugs' in var else None,
                } for var in data['dr_variants']+data['other_variants']]
            if rows==[]: return
            result = conn.execute(insert(variant_table).on_conflict_do_nothing(index_elements=['id']),rows)
            conn.commit()
            rows = [{'variant_id': "%(locus_tag)s_%(change)s" % var,'sample_id': data['id']} for var in data['dr_variants'] + data['other_variants']]
            result = conn.execute(insert(sample_variants_table),rows)
            conn.commit()

    meta = {}
    for row in csv.DictReader(open(args.metadata_csv)):
        row['id'] = row['wgs_id']
        row['country'] = row['country_code']
        row['date'] = row['date_of_collection']
        if row['country']=="N/A": del row['country']
        meta[row['wgs_id']] = row


    data = json.load(open(args.json))
    m = meta.get(data['id'])
    if m:
        data.update(m)

    ena_data = eq.get_ena_country(data)
    if ena_data['iso3']:
        data['iso_a3'] = ena_data['iso3']

    conf = pp.get_db('tbprofiler',args.db)
    data['drug_table'] = get_drug_table(data['dr_variants'],conf)
    for var in data['other_variants']:
        var['grading'] = {a['drug']:a['confidence'] for a in var['annotation']}

    for l in data['lineage']:
        del l['support']
    for var in data['dr_variants'] + data['other_variants'] + data['qc_fail_variants']:
        if 'annotation' in var:
            del var['annotation']
        if 'consequences' in var:
            del var['consequences']
    
    data['public'] = args.public

    add_sample(data)

# Set up the parser
parser = argparse.ArgumentParser(description='tbprofiler script',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--json',type=str,help='File with samples',required = True)
parser.add_argument('--db',default="tbdb",type=str,help='Database name')
parser.add_argument('--metadata-csv',type=str,help='Database name',required = True)
parser.add_argument('--db-pass',type=str,help='Database name',required = True)
parser.add_argument('--db-user',type=str,help='Database name',required = True)
parser.add_argument('--public',action="store_true",help='Is the sample public?')
parser.set_defaults(func=main)

args = parser.parse_args()
args.func(args)