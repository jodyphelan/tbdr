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
import tbprofiler as tbp
import tbdr
from neo4j import GraphDatabase
from uuid import uuid4
import datetime
import random

class get_neo4j_db:
	def __init__(self,uri=None,user=None,password=None):
		if uri and user and password:
			self.driver = GraphDatabase.driver(uri, auth=(user,password))
		else:
			self.driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "test"))
	def close(self):
		self.driver.close()

	def read(self,*args):
		with self.driver.session() as session:
			result = session.read_transaction(self._run_cmd,"\n".join(args))
			return result

	def write(self,*args):
		with self.driver.session() as session:
			result = session.write_transaction(self._run_cmd,"\n".join(args))

	@staticmethod
	def _run_cmd(tx,cmd):
		result = []
		for record in tx.run(cmd):
			result.append(dict(record))
		return result


def dict2proerties(d):
	return ", ".join(['%s:"%s"' % (k,v) for k,v in d.items()])

def read_neo4j_results(sample_id, neo4j_db=None, summary=False, conf=None):
	neo4j_db = neo4j_db if neo4j_db else get_neo4j_db()
	data = neo4j_db.read(
		"MATCH (s:Sample {id:'%s'})" % sample_id,
		"OPTIONAL MATCH (s) -[c:CONTAINS]-> (v:Variant)",
		"OPTIONAL MATCH (v) -[:CONFERS_RESISTANCE]-> (d:Drug)",
		"RETURN s,v,c,collect(d)"
	)

	results = {}
	results["id"] = data[0]["s"]["id"]
	results["sample_name"] = data[0]["s"]["sampleName"]
	results["lineage"] = json.loads(data[0]["s"]["lineageInfo"])
	results["main_lin"] = data[0]["s"]["mainLineage"]
	results["sublin"] = data[0]["s"]["subLineage"]
	results["drtype"] = data[0]["s"]["drtype"]
	results["timestamp"] = data[0]["s"]["timestamp"]
	results["qc"] = json.loads(data[0]["s"]["qc"])
	results["pipeline"] = json.loads(data[0]["s"]["pipeline"])
	results["tbprofiler_version"] = data[0]["s"]["tbprofilerVersion"]
	results["db_version"] = json.loads(data[0]["s"]["dbVersion"])
	results["dr_variants"] = []
	results["other_variants"] = []

	for v in data:
		if v["v"]:
			var = {
				"gene": v["v"]["gene"],
				"locus_tag": v["v"]["locus_tag"],
				"change": v["v"]["change"],
				"type": v["v"]["type"],
				"genome_pos": v["c"]["genome_pos"],
				"nucleotide_change": v["c"]["nucleotideChange"],
				"_internal_change": v["c"]["internalChange"],
				"freq": float(v["c"]["freq"]),
			}
			if len(v["collect(d)"])>0:
				var["drugs"] = []
				for d in v["collect(d)"]:
					d = dict(d)
					d["drug"] = d["id"]
					var["drugs"].append(d)
				results["dr_variants"].append(var)
			else:
				results["other_variants"].append(var)

	if summary:
		drug_order = ["isoniazid","rifampicin","ethambutol","pyrazinamide","streptomycin","ethionamide","fluoroquinolones","amikacin","capreomycin","kanamycin"]
		results = tbp.get_summary(results,conf,drug_order=drug_order)

	results["dr_variants"] = sorted(results["dr_variants"],key=lambda x:x["genome_pos"])
	results["other_variants"] = sorted(results["other_variants"],key=lambda x:x["genome_pos"])
	return results

def write_neo4j_results(results, neo4j_db):
	neo4j_db = neo4j_db if neo4j_db else get_neo4j_db()
	neo4j_db.write(
		"MERGE (s:Sample {id:'%s'})" % (results["id"]),
		"SET s.subLineage = '%s'" % (results["sublin"]),
		"SET s.mainLineage = '%s'" % (results["main_lin"]),
		"SET s.drtype = '%s'" % (results["drtype"]),
		"SET s.lineageInfo = '%s'" % (json.dumps(results["lineage"])),
		"SET s.qc = '%s'" % (json.dumps(results["qc"])),
		"SET s.pipeline = '%s'" % (json.dumps(results["pipeline"])),
		"SET s.tbprofilerVersion = '%s'" % results["tbprofiler_version"],
		"SET s.dbVersion = '%s'" % json.dumps(results["db_version"]),
		"REMOVE s:Processing"
	)
	for var in results["dr_variants"]+results["other_variants"]:
		if "nucleotide_change" not in var:
			var["nucleotide_change"] = "NA"
		neo4j_db.write(
			"MERGE (v:Variant {id:'%s_%s'})" % (var["locus_tag"], var["change"]),
			"SET v.gene = '%s'" % (var["gene"]),
			"SET v.locus_tag = '%s'" % (var["locus_tag"]),
			"SET v.change = '%s'" % (var["change"]),
			"SET v.type = '%s'" % (var["type"]),
			# "SET v.genomePos = '%s'" % (var["genome_pos"]),
			# "SET v.nucleotideChange = '%s'" % (var.get("nucleotide_change","")),
			# "SET v.internalChange = '%s'" % (var["_internal_change"]),
		)

		tmp_dict = {
			"freq": var["freq"], "genome_pos": var["genome_pos"],
			"nucleotide_change": var["nucleotide_change"],
			"internal_change": var["_internal_change"]
		}
		if "variant_annotations" in var:
			for k,v in var["variant_annotations"].items():
				tmp_dict[k] = v

		neo4j_db.write(

			"MATCH (s:Sample {id:'%s'}),(v:Variant {id:'%s_%s'}) " % (results["id"],var["locus_tag"],var["change"]),
			"CREATE (s) -[:CONTAINS { %s }]-> (v)" % dict2proerties(tmp_dict)
		)
		if "drugs" in var:
			for d in var["drugs"]:
				neo4j_db.write(
					"MATCH (v:Variant {id:'%s_%s'}) " % (var["locus_tag"],var["change"]),
					"MERGE (d:Drug {id:'%s'})" % (d["drug"]),
					"MERGE (v) -[:CONFERS_RESISTANCE]-> (d)"
				)


def get_conf_dict(library_prefix):
    files = {"gff":".gff","ref":".fasta","ann":".ann.txt","barcode":".barcode.bed","bed":".bed","json_db":".dr.json","version":".version.json"}
    conf = {}
    for key in files:
        sys.stderr.write("Using %s file: %s\n" % (key,library_prefix+files[key]))
        conf[key] = pp.filecheck(library_prefix+files[key])
    return conf

def main(args):
    # Get a dictionary with the database file: {"ref": "/path/to/fasta" ... etc. }
    conf = get_conf_dict(sys.base_prefix + "/share/tbprofiler/%s" % args.db)
    db = get_neo4j_db()
    # Get a dictionary mapping the locus_tags to drugs: {"Rv1484": ["isoniazid","ethionamide"], ... etc. }
    locus_tag2drugs = tbp.get_lt2drugs(conf["bed"])
    drugs2lt = tbp.get_drugs2lt(conf["bed"])
    
    # If a list of samples is supplied through the args object, store it in a list else get the list from looking in the results direcotry
    
    i = 0
    dst_rows = []
    # Loop through the sample result files
    for row in tqdm(csv.DictReader(open(args.meta))):
        s = row["wgs_id"]
        # Data has the same structure as the .result.json files
        data = json.load(open(pp.filecheck("%s/%s%s" % (args.dir,s,args.suffix))))
        uniq_id = str(uuid4())
        data["id"] = uniq_id
        date = datetime.datetime.now() - datetime.timedelta(days=random.randint(1,100))
        drug_line = ", ".join(["%s:'%s'" % (d.replace("-","_"),{"0":"S","1":"R"}.get(row[d],"NA")) for d in drugs2lt if d in row])
        db.write(f"CREATE (s:Sample:Private {{ id:'{uniq_id}', sampleName:'{s}', timestamp:'{date.isoformat()}', userID:'{args.user_id}', {drug_line}}})")
        write_neo4j_results(data,db)
        tmp = {"Run ID":uniq_id}
        for d in drugs2lt:
            if d in row:
                tmp[d] = row[d]
        dst_rows.append(tmp)
        i+=1
        if i>args.max_entries:
            break

    with open(args.outfile,"w") as O:
        writer = csv.DictWriter(O,fieldnames= list(dst_rows[0]))
        writer.writeheader()
        writer.writerows(dst_rows)


# Set up the parser
parser = argparse.ArgumentParser(description='tbprofiler script',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--outfile',type=str,help='File with samples',required=True)
parser.add_argument('--meta',type=str,help='File with samples',required=True)
parser.add_argument('--dir',default="results/",type=str,help='Directory containing results')
parser.add_argument('--db',default="tbdb",type=str,help='Database name')
parser.add_argument('--suffix',default=".results.json",type=str,help='File suffix')
parser.add_argument('--user-id',default="1",type=str,help='User ID')
parser.add_argument('--max-entries',default=100,type=str,help='User ID')
parser.set_defaults(func=main)

args = parser.parse_args()
args.func(args)
