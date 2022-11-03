from flask import (
	Blueprint, flash, g, redirect, render_template, request, url_for, Response
)
from werkzeug.exceptions import abort
import json
# from tbdr.auth import login_required
import tbprofiler as tbp
import sys
from flask import current_app as app
from collections import defaultdict, Counter
from .db import db_session
bp = Blueprint('variants', __name__)

gene2locus_tag = {}
for l in open(sys.base_prefix + "/share/tbprofiler/tbdb.bed"):
	row = l.strip().split()
	gene2locus_tag[row[4]] = row[3]
	gene2locus_tag[row[3]] = row[3]

def get_variant_data(gene,variant):


	sample_data =  neo4j.read("MATCH (s:SRA) -[:CONTAINS]-> (v:Variant {id:'%s_%s'}) RETURN s.drtype AS `Drug resistance`,s.lineage as Lineage, count(*) as Count" % (gene2locus_tag[gene],variant))
	stats = neo4j.read("MATCH (v:Variant {id:'%s_%s'}) return v.support" % (gene,variant))
	if len(stats)>=1:
		stats = stats[0]
	else:
		stats = None
	stats = json.loads(stats["v.support"]) if (stats and stats["v.support"] != None) else []
	return {"sample_data":sample_data,"support":stats}

def get_variant_stats(gene,variant):
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
	locus_tag = gene2locus_tag[gene]
	sample_data =  db_session.execute("SELECT * FROM sample_variants LEFT JOIN samples ON sample_variants.sample_id = samples.id WHERE variant_id = '%s_%s';" % (gene2locus_tag[gene],variant)).fetchall()
	if add_links:
		for i,d in enumerate(sample_data):
			d = dict(d)
			d["sample_link"] = '<a href="%s">%s</a>' % (url_for('results.run_result',sample_id=d["id"]),d["id"])
			sample_data[i] = d
	print(sample_data)
	return sample_data

def query_variants(raw_queries):
	queries = []

	for t in raw_queries:
		if len([x for x in t[1] if x!=""])>0:
			queries.append("(%s)" %" OR ".join(["%s='%s'" % (t[0],x) for x in t[1]]))
	query = " AND ".join(queries)
	data = db_session.execute("SELECT * from variants WHERE %s" % query).fetchall()
	new_data = []
	for x in data:
		x = dict(x)
		x["variant_link"] = '<a href="%s">%s</a>' % (url_for('variants.variant',gene=x["gene"],variant=x["change"]),x["change"])
		new_data.append(x)
	return new_data

def uniq(l):
	return list(set(l))

@bp.route('/variants',methods=('GET', 'POST'))
def browse():
	gene_data = db_session.execute("SELECT * FROM VARIANTS;").fetchall()
	genes = sorted(uniq([d["gene"] for d in gene_data]))
	locus_tags = sorted(uniq([d["locus_tag"] for d in gene_data]))
	variant_types = db_session.execute("SELECT type, COUNT(*) as count FROM variants GROUP BY type;").fetchall()
	data = None
	if request.method == 'POST':
		data = query_variants(request.form.lists())
	return render_template('variants/variant_home.html', genes = genes, locus_tags = locus_tags, variant_types=variant_types, data = data)


@bp.route('/variants/<gene>/<variant>',methods=('GET', 'POST'))
def variant(gene,variant):
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

	# support_data = get_variant_stats(gene,variant)


	raw_geojson = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	country2total_count = dict(db_session.execute('SELECT country, COUNT(*) as count FROM samples GROUP BY country;').fetchall())
	country2variant_count = Counter([d["country"] for d in data])
	geojson = {"type":"FeatureCollection", "features":[]}
	isolates_with_country = 0
	for f in raw_geojson["features"]:
		country = f["properties"]["iso_a2"].lower()
		if country in country2variant_count:
			f["properties"]["variant"] = country2variant_count[country] / country2total_count[country]
			geojson["features"].append(f)
			isolates_with_country += country2variant_count[country]

	return render_template('variants/variant.html',gene=gene,variant = variant,dr_counts = dr_counts,geojson=geojson,lineage_counts = lineage_counts,isolates_with_country=isolates_with_country, sample_data = data)


@bp.route('/variants/json/<gene>/<variant>')
def variant_json(gene,variant):
	return json.dumps(get_variant_data(gene,variant))
