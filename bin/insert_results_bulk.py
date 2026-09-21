#! /usr/bin/env python

# Load useful libraries
import json
import argparse
import csv
import os
import sys
import pathogenprofiler as pp
from glob import glob
from tqdm import tqdm
from tbdr import create_app
from tbdr.models import Result, Sample, Variant, SampleVariant, Drug, VariantDrugConfidence, Collection, SampleCollectionLink
from tbdr.db import get_db_session
from sqlalchemy.dialects.postgresql import insert



# Set up the parser
parser = argparse.ArgumentParser(description='tbprofiler script',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--dir',type=str,help='Folder with samples',required = True)
parser.add_argument('--db',default="who_v3",type=str,help='Database name')
parser.add_argument('--metadata', dest='metadata', type=str, help='Metadata CSV file', required=True)
parser.add_argument('--public',action='store_true',help='Use the public database')
parser.add_argument('--batch-size',type=int,default=100,help='Batch size for processing JSON files')
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

meta = {}
for row in csv.DictReader(open(args.metadata,encoding='utf-8-sig')):
    for key in ['iso_a3','country','year_of_collection']:
        if row[key] == '':
            row[key] = None


    meta[row['id']] = row

app = create_app()

with app.app_context():
    db_session = get_db_session()




    collection_row = {
        'name': 'public',
        'description': 'Public collection of samples'
    }
    # add the public collection if it doesn't exist
    if not Collection.query.filter_by(name='public').first():
        db_session.add(Collection(**collection_row)) 
        db_session.commit()
    public_collection_id = Collection.query.filter_by(name='public').first().id

    json_files = glob(args.dir + "/*.json")
    print(f"Found {len(json_files)} JSON files in {args.dir}. Processing in batches of {args.batch_size}.")

    batches = [json_files[i:i + args.batch_size] for i in range(0, len(json_files), args.batch_size)]
    for batch in tqdm(batches):
        result_rows = []
        sample_rows = []
        variant_rows = set()
        sample_variant_rows = []
        drug_rows = set()
        variant_drugs_rows = []
        sample_collection_rows = []
        for json_file in batch:
            with open(json_file) as f:
                data = json.loads(f.read().replace("comments","comment"))
            data['drug_table'] = get_drug_table(data['dr_variants'],conf)
            for var in data['other_variants']:
                var['grading'] = {a['drug']:a['confidence'] for a in var['annotation']}

            sample_meta = meta.get(data['id'],{})
            result_row = {
                'data': data,
                'sample_id': data['id'],
                'status': 'completed'
            }
            result_rows.append(result_row)

            sample_row = {
                'id': data['id'],
                'sample_name': data['id'],
                'lineage': data['main_lineage'],
                'drtype': data['drtype'],
                'iso_a3': sample_meta.get('iso_a3',None),
                'country': sample_meta.get('country',None),
                'year_of_collection': sample_meta.get('year_of_collection',None),
            }
            sample_rows.append(sample_row)

            for var in data['dr_variants']+data['other_variants']:
                variant_row = {
                    'id': f"{var['locus_tag']}:{var['change']}",
                    'gene': var['gene_name'],
                    'locus_tag': var['gene_id'],
                    'type': var['type'],
                    'change': var['change'],
                }
                variant_rows.add(json.dumps(variant_row))

                sample_variant_row = {
                    'sample_id': data['id'],
                    'variant_id': variant_row['id'],
                    'frequency': var['freq'],
                    'depth': var['depth']
                }
                sample_variant_rows.append(sample_variant_row)

                if 'drugs' in var:
                    for d in var['drugs']:
                        confidence_row = {
                            'variant_id': variant_row['id'],
                            'drug_id': d['drug'],
                            'confidence': d['confidence'],
                            'source': d['source'],
                            'comment': d['comment'] if d['comment']!="" else None
                        }
                        drug_rows.add(json.dumps({'id': d['drug']}))
                        variant_drugs_rows.append(confidence_row)
                elif 'annotation' in var:
                    for a in var['annotation']:
                        if a['type'] == 'who_confidence':
                            confidence_row = {
                                'variant_id': variant_row['id'],
                                'drug_id': a['drug'],
                                'confidence': a['confidence'],
                                'source': a['source'],
                                'comment': a['comment'] if a['comment']!="" else None
                            }
                            drug_rows.add(json.dumps({'id': a['drug']}))
                            variant_drugs_rows.append(confidence_row)


            if args.public:
                sample_collection_row = {
                    'sample_id': data['id'],
                    'collection_id': public_collection_id
                }
                sample_collection_rows.append(sample_collection_row)

        rehydrated_variant_rows = [json.loads(v) for v in variant_rows]
        rehydrated_drug_rows = [json.loads(d) for d in drug_rows]

        stmt = insert(Sample).values(sample_rows).on_conflict_do_nothing(index_elements=['id'])
        db_session.execute(stmt)
        stmt = insert(Result).values(result_rows).on_conflict_do_nothing(index_elements=['id'])
        db_session.execute(stmt)
        stmt = insert(Variant).values(rehydrated_variant_rows).on_conflict_do_nothing(index_elements=['id'])
        db_session.execute(stmt)
        stmt = insert(SampleVariant).values(sample_variant_rows).on_conflict_do_nothing(index_elements=['sample_id', 'variant_id'])
        db_session.execute(stmt)
        stmt = insert(Drug).values(rehydrated_drug_rows).on_conflict_do_nothing(index_elements=['id'])
        db_session.execute(stmt)
        stmt = insert(VariantDrugConfidence).values(variant_drugs_rows).on_conflict_do_nothing(index_elements=['variant_id', 'drug_id'])
        db_session.execute(stmt)

        if len(sample_collection_rows) > 0:
            stmt = insert(SampleCollectionLink).values(sample_collection_rows).on_conflict_do_nothing(index_elements=['sample_id', 'collection_id'])
            db_session.execute(stmt)

        db_session.commit()



            
