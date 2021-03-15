import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext
from neo4j import GraphDatabase
import json
import tbprofiler as tbp

class get_neo4j_db:
	def __init__(self,uri=None,user=None,password=None):
		if uri and user and password:
			self.driver = GraphDatabase.driver(uri, auth=(user,password))
		else:
			self.driver = GraphDatabase.driver(current_app.config['NEO4J_URI'], auth=(current_app.config['NEO4J_USER'], current_app.config['NEO4J_PASSWORD']))
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
	print(data)
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
		print(var)
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


def tbdr_get_mutation_info(gene,mutation):
	print("Getting mutation metadata")
	data = json.loads(urlopen("http://localhost:5000/variants/json/%s/%s" % (gene,mutation)).read())
	drtype = defaultdict(int)
	lineage = defaultdict(int)
	for row in data["sample_data"]:
		drtype[row["Drug resistance"]] += row["Count"]
		if row["Lineage"]==None: continue
		if ";" in row["Lineage"]: continue
		lineage[row["Lineage"]] += row["Count"]
	return {"drtype":drtype,"lineage":lineage, "support":data["support"]}
