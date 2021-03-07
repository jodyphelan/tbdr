from flask import (
	Blueprint, flash, g, redirect, render_template, request, url_for, Response
)
from werkzeug.exceptions import abort
import json
# from tbdr.auth import login_required
from tbdr.db import  get_neo4j_db
import tbprofiler as tbp
import sys
from flask import current_app as app
from collections import defaultdict, Counter

bp = Blueprint('variants', __name__)

gene2locus_tag = {}
for l in open(sys.base_prefix + "/share/tbprofiler/tbdb.bed"):
	row = l.strip().split()
	gene2locus_tag[row[4]] = row[3]
	gene2locus_tag[row[3]] = row[3]

def get_variant_data(gene,variant):
	neo4j = get_neo4j_db()


	sample_data =  neo4j.read("MATCH (s:SRA) -[:CONTAINS]-> (v:Variant {id:'%s_%s'}) RETURN s.drtype AS `Drug resistance`,s.lineage as Lineage, count(*) as Count" % (gene2locus_tag[gene],variant))
	stats = neo4j.read("MATCH (v:Variant {id:'%s_%s'}) return v.support" % (gene,variant))
	if len(stats)>=1:
		stats = stats[0]
	else:
		stats = None
	stats = json.loads(stats["v.support"]) if (stats and stats["v.support"] != None) else []
	return {"sample_data":sample_data,"support":stats}

def get_variant_stats(gene,variant):
	neo4j = get_neo4j_db()
	stats = neo4j.read("MATCH (v:Variant {id:'%s_%s'}) return v.support" % (gene,variant))
	if len(stats)>=1:
		stats = stats[0]
	else:
		stats = None
	print(stats)
	tmp = json.loads(stats["v.support"]) if (stats and stats["v.support"] != None) else []
	stats = []
	for d in tmp:
		for k in d:
			if isinstance(d[k],float):
				if d[k]<0.01:
					d[k] = "%.2e" % d[k]
				else:
					d[k] = "%.2f" % d[k]
		stats.append(d)
	return stats

def get_variant_samples(gene,variant,add_links=True):
	neo4j_db = get_neo4j_db()
	locus_tag = gene2locus_tag[gene]
	sample_data =  neo4j_db.read("MATCH (v:Variant {id:'%s_%s'}) <-[:CONTAINS]- (s:SRA) RETURN s.id as id, s.drtype as drtype ,s.lineage as lineage, s.spoligotype as spoligotype, s.countryCode as country_code" % (gene2locus_tag[gene],variant))
	if add_links:
		for d in sample_data:
			d["sample_link"] = '<a href="%s">%s</a>' % (url_for('results.run_result',sample_id=d["id"]),d["id"])
	return sample_data

def query_variants(raw_queries):
	neo4j_db = get_neo4j_db()
	queries = []

	for t in raw_queries:
		if len([x for x in t[1] if x!=""])>0:
			queries.append("(%s)" %" OR ".join(["n.%s='%s'" % (t[0],x) for x in t[1]]))
	query = " AND ".join(queries)
	data = neo4j_db.read("MATCH (n:Variant ) WHERE %s OPTIONAL MATCH (n) -[:CONFERS_RESISTANCE]-> (d:Drug) RETURN n.id as id,n.gene as gene, n.locus_tag as locus_tag, n.type as type, n.change as change, d.id as drug" % query)
	tmp_data = defaultdict(list)

	for x in data:
		x["variant_link"] = '<a href="%s">%s</a>' % (url_for('variants.variant',gene=x["gene"],variant=x["change"]),x["change"])
		drug = x["drug"]
		tmp_data[json.dumps({key:value for key,value in x.items() if key!="drug"})].append(drug)
	new_data = []
	for x in tmp_data:
		d = json.loads(x)
		d["drugs"] = ", ".join([z for z in tmp_data[x] if z])
		new_data.append(d)

	return new_data

@bp.route('/variants',methods=('GET', 'POST'))
def browse():
	neo4j = get_neo4j_db()
	gene_data = neo4j.read("MATCH (g:Gene) RETURN g.locusTag as locus_tag, g.name as gene")
	genes = sorted([d["gene"] for d in gene_data])
	locus_tags = sorted([d["locus_tag"] for d in gene_data])
	variant_types = neo4j.read("MATCH (v:Variant) RETURN v.type as type, count(*) as count")
	data = None
	if request.method == 'POST':
		data = query_variants(request.form.lists())
	return render_template('variants/variant_home.html', genes = genes, locus_tags = locus_tags, variant_types=variant_types, data = data)


@bp.route('/variants/<gene>/<variant>',methods=('GET', 'POST'))
def variant(gene,variant):
	neo4j = get_neo4j_db()
	if "query" in request.form:
		query =request.form["query_values"]
		gene,variant = query.split("_")
		data = get_variant_samples(gene,variant,add_links=False)
		csv_strings = [",".join([str(y) for y in x.values()]) for x in data]
		csv_strings.insert(0,",".join(list(data[0])))
		csv_text = "\n".join(csv_strings)
		return Response(csv_text,mimetype="text/csv",headers={"Content-disposition": "attachment; filename=test.csv"})
	data = get_variant_samples(gene,variant)
	dr_counts = dict(Counter([d["drtype"] for d in data]))
	dr_counts = {k:dr_counts.get(k,0) for k in ["Sensitive","Pre-MDR","MDR","Pre-XDR","XDR","Other"]}
	lineage_counts = Counter({d["lineage"] for d in data})

	support_data = get_variant_stats(gene,variant)


	raw_geojson = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	data_country = neo4j.read(
		"MATCH (s:SRA) -[:COLLECTED_IN]-> (c:Country) RETURN c.id as country, count(*) as count"
	)


	country2variant_count = Counter([d["country_code"] for d in data])
	country2total_count = {x:y for x,y in [d.values() for d in data_country]}
	geojson = {"type":"FeatureCollection", "features":[]}
	isolates_with_country = 0
	for f in raw_geojson["features"]:
		country = f["properties"]["iso_a2"].lower()
		if country in country2variant_count:
			f["properties"]["variant"] = country2variant_count[country] / country2total_count[country]
			geojson["features"].append(f)
			isolates_with_country += country2variant_count[country]
			# import pdb; pdb.set_trace()

	return render_template('variants/variant.html',gene=gene,variant = variant,dr_counts = dr_counts,geojson=geojson,lineage_counts = lineage_counts, support=support_data,isolates_with_country=isolates_with_country, sample_data = data)


@bp.route('/variants/json/<gene>/<variant>')
def variant_json(gene,variant):
	return json.dumps(get_variant_data(gene,variant))
