import json
from tbprofiler.models import ProfileResult
import datetime
import pathogenprofiler as pp
import argparse

argparser = argparse.ArgumentParser(description='Migrate tbdr results to tbprofiler',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
argparser.add_argument('input',type=str,help='JSON file with tbdr results')
argparser.add_argument('output',type=str,help='Output JSON file')
args = argparser.parse_args()

rawdata = json.load(open(args.input))

lineage_recoded = []
for lin in rawdata["lineage"]:
    d = {
        'fraction': lin['frac'],
        'lineage': lin['lin'],
        'family': lin['family'],
        'rd': lin['rd'],
        'support': []
    }
    lineage_recoded.append(d)


dr_variants_recoded = []
for var in rawdata["dr_variants"]:
    drgs = []
    for d in var['drugs']:
        nd = {
            'type': 'drug_resistance',
            'drug': d['drug'],
            'confidence': d.get('who confidence','Uncertain significance'),
            'source': None,
            'comment': "",

        }
        drgs.append(nd)
    d = {
        'chrom': var['chrom'],
        'pos': var['genome_pos'],
        'ref': var['ref'],
        'alt': var['alt'],
        'depth': var['depth'],
        'freq': var['freq'],
        'sv': True if var['alt'] == '<DEL>' else False,
        'filter': 'pass',
        'forward_reads': None,
        'reverse_reads': None,
        'sv_len': None,
        'gene_id': var['locus_tag'],
        'gene_name': var['gene'],
        'type': var['type'],
        'change': var['change'],
        'nucl_change': var['nucleotide_change'],
        'protein_change': var['protein_change'],
        'annotation': [],
        'consequences': [],
        'drugs': drgs,
        'locus_tag': var['locus_tag'],
        'gene_associated_drugs': var['gene_associated_drugs'],
    }
    dr_variants_recoded.append(d)


other_variants_recoded = []
for var in rawdata["other_variants"]:
    grading = {}
    anns = []
    if 'annotation' in var:
        for d in var['annotation']:
            nd = {
                'type': 'who_confidence',
                'drug': d['drug'],
                'confidence': d.get('who confidence','Uncertain significance'),
                'source': None,
                'comment': "",

            }
            anns.append(nd)
            grading[d['drug']] = d['who_confidence']
    d = {
        'chrom': var['chrom'],
        'pos': var['genome_pos'],
        'ref': var['ref'],
        'alt': var['alt'],
        'depth': var['depth'],
        'freq': var['freq'],
        'sv': True if var['alt'] == '<DEL>' else False,
        'filter': 'pass',
        'forward_reads': None,
        'reverse_reads': None,
        'sv_len': None,
        'gene_id': var['locus_tag'],
        'gene_name': var['gene'],
        'type': var['type'],
        'change': var['change'],
        'nucl_change': var['nucleotide_change'],
        'protein_change': var['protein_change'],
        'annotation': anns,
        'consequences': [],
        'locus_tag': var['locus_tag'],
        'gene_associated_drugs': var['gene_associated_drugs'],
        'grading': {d:grading.get(d) for d in var['gene_associated_drugs']}
    }
    other_variants_recoded.append(d)


newdata = {
    'id': rawdata['id'],
    'timestamp': rawdata['timestamp'],
    'pipeline': {
        'software_version': rawdata['tbprofiler_version'],
        'db_version': rawdata['db_version'],
        'software': [
            {
                'process': 'variant_calling',
                'software': 'freebayes',
            }
        ]
    },
    'notes': [],
    'lineage': lineage_recoded,
    'main_lineage': rawdata['main_lin'],
    'sub_lineage': rawdata['sublin'],
    'spoligotype': None,
    'drtype': rawdata['drtype'],
    'dr_variants': dr_variants_recoded,
    'other_variants': other_variants_recoded,
    'qc': {
        'percent_reads_mapped': rawdata['qc']['pct_reads_mapped'],
        'num_reads_mapped': rawdata['qc']['num_reads_mapped'],
        'target_median_depth': rawdata['qc']['median_coverage'],
        'genome_median_depth': rawdata['qc']['median_coverage'],
        'target_qc': [],
    },
    'missing_positions': [],
    'linked_samples': [],
    'migrated': True,
}

res = newdata


def get_drug_table(dr_variants,drugs):
    all_drugs = drugs
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

drugs = [
    "rifampicin",
    "isoniazid",
    "ethambutol",
    "pyrazinamide",
    "streptomycin",
    "fluoroquinolones",
    "moxifloxacin",
    "ofloxacin",
    "levofloxacin",
    "ciprofloxacin",
    "aminoglycosides",
    "amikacin",
    "capreomycin",
    "kanamycin",
    "cycloserine",
    "ethionamide",
    "clofazimine",
    "para-aminosalicylic_acid",
    "delamanid",
    "bedaquiline",
    "linezolid"
  ]

res['drug_table'] = get_drug_table(dr_variants_recoded, drugs)


json.dump(res, open(args.output, 'w'), indent=2)