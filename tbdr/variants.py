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
from sqlalchemy import text

bp = Blueprint('variants', __name__)

gene2locus_tag = {}
for l in open(sys.base_prefix + "/share/tbprofiler/tbdb.bed"):
	row = l.strip().split()
	gene2locus_tag[row[4]] = row[3]
	gene2locus_tag[row[3]] = row[3]


def get_variant_samples(gene,variant,add_links=True):
	sample_data =  db_session.execute(text("SELECT * FROM sample_variants LEFT JOIN samples ON sample_variants.sample_id = samples.id WHERE variant_id = '%s_%s';" % (gene2locus_tag[gene],variant))).fetchall()
	if add_links:
		for i,d in enumerate(sample_data):
			d = d._asdict()
			d["sample_link"] = '<a href="%s">%s</a>' % (url_for('results.run_result',sample_id=d["id"]),d["id"])
			sample_data[i] = d

	return sample_data

def query_variants(raw_queries):
	queries = []

	for t in raw_queries:
		if len([x for x in t[1] if x!=""])>0:
			queries.append("(%s)" %" OR ".join(["%s='%s'" % (t[0],x) for x in t[1]]))
	query = " AND ".join(queries)
	data = db_session.execute(text("SELECT * from variants WHERE %s" % query)).fetchall()

	new_data = []
	for row in data:
		x = row._asdict()
		
		x['variant_link'] = '<a href="%s">%s</a>' % (url_for('variants.variant',gene=row.gene,variant=row.change),row.change)
		new_data.append(x)
	return new_data

def uniq(l):
	return list(set(l))

@bp.route('/variants',methods=('GET', 'POST'))
def browse():
	# gene_data = db_session.execute(text("SELECT * FROM VARIANTS;")).fetchall()
	# select distinct genes from db
	gene_data = db_session.execute(text("SELECT DISTINCT gene,locus_tag FROM variants;")).fetchall()
	genes = sorted(uniq([d[0] for d in gene_data]))
	locus_tags = sorted(uniq([d[1] for d in gene_data]))


	variant_types = db_session.execute(text("SELECT DISTINCT type FROM variants;")).fetchall()
	data = None
	if request.method == 'POST':
		data = query_variants(request.form.lists())
	return render_template('variants/variant_home.html', genes = genes, locus_tags = locus_tags, variant_types=variant_types, data = data)


@bp.route('/variants/<gene>/<variant>',methods=('GET', 'POST'))
def variant(gene,variant):
	if "query" in request.form:
		query =request.form["query_values"]
		print(query)
		tmp = query.split("_")
		gene = tmp[0]
		variant = "_".join(tmp[1:])
		data = get_variant_samples(gene,variant,add_links=False)
		print(data)
		csv_strings = [",".join([str(x[i]) for i in [1,0,2,7,8,10]]) for x in data]
		csv_strings.insert(0,",".join(['Accession','Genome position','Variant','DR type','Lineage','Country code']))
		csv_text = "\n".join(csv_strings)
		return Response(csv_text,mimetype="text/csv",headers={"Content-disposition": "attachment; filename=test.csv"})
	data = get_variant_samples(gene,variant)
	dr_counts = dict(Counter([d["drtype"] for d in data]))
	dr_counts = {k:dr_counts.get(k,0) for k in ["Sensitive","Pre-MDR","MDR","Pre-XDR","XDR","Other"]}
	lineage_counts = Counter({d["lineage"] for d in data})

	# support_data = get_variant_stats(gene,variant)


	raw_geojson = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	country2total_count = dict(db_session.execute(text('SELECT country, COUNT(*) as count FROM samples GROUP BY country;')).fetchall())
	country2variant_count = Counter([d["country"] for d in data])
	geojson = {"type":"FeatureCollection", "features":[]}
	isolates_with_country = 0
	for f in raw_geojson["features"]:
		country = f["properties"]["iso_a3"].lower()
		if country in country2variant_count:
			f["properties"]["variant"] = country2variant_count[country] / country2total_count[country]
			geojson["features"].append(f)
			isolates_with_country += country2variant_count[country]

	return render_template('variants/variant.html',gene=gene,variant = variant,dr_counts = dr_counts,geojson=geojson,lineage_counts = lineage_counts,isolates_with_country=isolates_with_country, sample_data = data)



