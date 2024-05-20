from flask import (
	Blueprint,  render_template, request, url_for, Response
)
import json
# from tbdr.auth import login_required
from flask import current_app as app
from collections import Counter
bp = Blueprint('sra', __name__)
import sys
import csv
from .db import db_session
from sqlalchemy import text

def get_geojson(country_counts):
	raw_geojson = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	geojson = {"type":"FeatureCollection", "features":[]}

	for f in raw_geojson["features"]:
		country = f["properties"]["iso_a2"]
		if country in country_counts:
			f["properties"]["num_isolates"] = country_counts[country]
			geojson["features"].append(f)

	return geojson


@bp.route('/sra',methods=('GET', 'POST'))
def sra():

	country_counts = dict(db_session.execute(text("SELECT country, COUNT(*) FROM samples WHERE public = true GROUP BY country")).fetchall())
	dr_counts = db_session.execute(text("SELECT drtype, COUNT(*) FROM samples WHERE public = true GROUP BY drtype")).fetchall()
	lineage_counts = db_session.execute(text("SELECT lineage, COUNT(*) FROM samples WHERE public = true GROUP BY lineage")).fetchall()
	print(dr_counts[0]._asdict())
	dr_order = {"Sensitive":1,"RR-TB":2,"HR-TB":3,"MDR-TB":4,"Pre-XDR-TB":5,"XDR-TB":6,"Other":7}
	dr_data = sorted(dr_counts ,key=lambda x:dr_order[x._asdict()["drtype"]])
	
	raw_geojson = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	geojson = {"type":"FeatureCollection", "features":[]}
	print(country_counts)
	for f in raw_geojson["features"]:
		country = f["properties"]["iso_a2"].lower()
		print(country)
		if country in country_counts:
			f["properties"]["num_isolates"] = country_counts[country]
			geojson["features"].append(f)
	print(lineage_counts)





	return render_template('sra/landing.html', dr_data=dr_data, geojson=geojson, top_mutations = None, lineage_counts=lineage_counts)

@bp.route('/sra/country')
def country():
	return "Add country to see country data"

@bp.route('/sra/country/<country>')
def country_data(country):
	data = query_samples([("country",[country])])
	country_code = data[0]["country_code"]
	top_mutations = db_session.execute(text("SELECT gene, change, count, drugs FROM (SELECT variant_id, count(*) as count FROM sample_variants WHERE sample_id IN (SELECT id FROM samples WHERE country = '%s') AND variant_id IN (SELECT id FROM variants WHERE drugs IS NOT NULL) GROUP BY sample_variants.variant_id ORDER BY count DESC LIMIT 10) t LEFT JOIN variants ON t.variant_id = variants.id;" % country_code)).fetchall()
	top_mutations = [x._asdict() for x in top_mutations]
	geojson = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	country_data = {}
	for row in csv.DictReader(open(app.config["APP_ROOT"]+url_for('static', filename='TB_burden_countries_2020-10-08.csv'))):
		if row["iso2"]==country_code.upper():
			country_data = row

	return render_template('sra/country.html', data=data,top_mutations=top_mutations,geojson = geojson,country=country, country_code = country_code, country_data = country_data, country_file = url_for('static', filename='TB_burden_countries_2020-10-08.csv'))

def query_samples(raw_queries,sample_links = True):
	queries = []
	tmp = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	admin_to_iso_a2 = {y["properties"]["admin"]:y["properties"]["iso_a2"] for y in tmp["features"]}

	for t in raw_queries:
		if t[0]=="country":
			queries.append("(%s)" %" OR ".join(["country='%s'" % (admin_to_iso_a2[x].lower()) for x in t[1]]))
		else:
			if len([x for x in t[1] if x!=""])>0:
				queries.append("(%s)" %" OR ".join(["%s='%s'" % (t[0],x) for x in t[1]]))
	query = "WHERE "+" AND ".join(queries) if len(queries)>0 else ""

	data = db_session.execute(text("SELECT id, country as country_code, drtype, lineage FROM SAMPLES %s" % query)).fetchall()
	print("asdasd")
	print([x._asdict() for x in data])
	data = [x._asdict() for x in data]
	if sample_links:
		for d in data:
			print(d)
			d["sample_link"] = '<a href="%s">%s</a>' % (url_for('results.run_result',sample_id=d["id"]),d["id"])
	return data

@bp.route('/sra/browse',methods=('GET', 'POST'))
def browse():
	tmp = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	country_list = sorted([y["properties"]["admin"] for y in tmp["features"]])
	lineages = sorted(list(set([l.strip().split()[3] for l in open(sys.base_prefix+"/share/tbprofiler/tbdb.barcode.bed")])))
	if request.method == 'POST':
		if "query" in request.form:
			data = query_samples(json.loads(request.form["query_values"]),sample_links=False)
			csv_strings = [",".join([str(y) for y in x.values()]) for x in data]
			csv_strings.insert(0,",".join(list(data[0])))
			csv_text = "\n".join(csv_strings)
			return Response(csv_text,mimetype="text/csv",headers={"Content-disposition": "attachment; filename=test.csv"})
		else:
			print(list(request.form.lists()))
			data = query_samples(request.form.lists())
			geojson = get_geojson(Counter([x["country_code"].upper() for x in data if x["country_code"]]))
			print(data)
			return render_template('sra/browse.html', data = data , geojson=geojson, countries = country_list,lineages=lineages, query=json.dumps(list(request.form.lists())))

	return render_template('sra/browse.html', data = None, countries=country_list,lineages=lineages)
