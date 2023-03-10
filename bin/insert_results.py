#! /usr/bin/env python

# Load useful libraries
import json
from collections import defaultdict
import argparse
import os
from tqdm import tqdm
import sys
import csv
import pathogenprofiler as pp
import tbprofiler
from copy import copy


def main(args):
    from sqlalchemy import create_engine
    engine = create_engine(f"postgresql+psycopg2://{args.db_user}:{args.db_pass}@localhost", echo=False)
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
            data['lineage'] = data['sublin']
            sample_id = data['id']
            result = conn.execute(insert(samples_table),data)
            conn.commit()
            stmt = insert(results_table).values(data=json_data,sample_id=sample_id)
            result = conn.execute(stmt)
            conn.commit()
            rows = [
                {
                    'id': "%(locus_tag)s_%(change)s" % var,
                    'gene':var['gene'],
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
    data['public'] = True

    add_sample(data)

# Set up the parser
parser = argparse.ArgumentParser(description='tbprofiler script',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--json',type=str,help='File with samples',required = True)
parser.add_argument('--db',default="tbdb",type=str,help='Database name')
parser.add_argument('--metadata-csv',type=str,help='Database name',required = True)
parser.add_argument('--db-pass',type=str,help='Database name',required = True)
parser.add_argument('--db-user',type=str,help='Database name',required = True)
parser.set_defaults(func=main)

args = parser.parse_args()
args.func(args)