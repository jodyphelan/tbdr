from flask import (
	Blueprint, flash, g, redirect, render_template, request, url_for, Response
)
from werkzeug.exceptions import abort
import json
# from tbdr.auth import login_required
from tbdr.db import  get_neo4j_db
import tbprofiler as tbp
from flask import current_app as app
from collections import Counter
bp = Blueprint('sra', __name__)
import sys
import csv
from datetime import datetime

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
	neo4j_db = get_neo4j_db()
	data = neo4j_db.read("MATCH (n:SRA) WHERE NOT n.drtype IS null return n.drtype as drtype, n.lineage as lineage, n.countryCode as country")
	dr_order = {"Sensitive":1,"Pre-MDR":2,"MDR":3,"Pre-XDR":4,"XDR":5,"Other":6,"Drug-resistant":7}
	dr_data = sorted([{"drtype":d[0],"count":d[1]} for d in dict(Counter([d["drtype"] for d in data])).items()] ,key=lambda x:dr_order[x["drtype"]])
	country_data = neo4j_db.read("MATCH (s:SRA) return s.countryCode as country, count(*) as count")
	country2total_count = {country.upper():count for country,count in [list(d.values()) for d in country_data] if country!=None}
	raw_geojson = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	geojson = {"type":"FeatureCollection", "features":[]}

	for f in raw_geojson["features"]:
		country = f["properties"]["iso_a2"]
		if country in country2total_count:
			f["properties"]["num_isolates"] = country2total_count[country]
			geojson["features"].append(f)

	top_mutations = neo4j_db.read(
		"MATCH (s:SRA)-[:CONTAINS]->(v:Variant) -[:CONFERS_RESISTANCE]-> ()",
		"RETURN v.gene as Gene, v.locus_tag as `Locus tag`, v.type as Type, v.change as Variant, count(s) as Count",
		"ORDER BY Count DESC LIMIT 10"
	)




	return render_template('sra/landing.html', dr_data=dr_data, geojson=geojson, top_mutations = top_mutations, data=data)

@bp.route('/sra/country')
def country():
	return "Add country to see country data"

@bp.route('/sra/country/<country>')
def country_data(country):
	neo4j_db = get_neo4j_db()
	data = query_samples([("country",[country])])
	country_code = data[0]["country_code"]
	top_mutations = neo4j_db.read(
		"MATCH (c:Country {id: '%s'}) <-[:COLLECTED_IN]- (s:SRA)-[:CONTAINS]->(v:Variant) -[:CONFERS_RESISTANCE]-> ()" % country_code.lower(),
		"RETURN v.gene as Gene, v.locus_tag as `Locus tag`, v.type as Type, v.change as Variant, count(s) as Count",
		"ORDER BY Count DESC LIMIT 10"
	)
	geojson = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	country_data = {}
	for row in csv.DictReader(open(app.config["APP_ROOT"]+url_for('static', filename='TB_burden_countries_2020-10-08.csv'))):
		if row["iso2"]==country_code.upper():
			country_data = row

	return render_template('sra/country.html', data=data,top_mutations=top_mutations,geojson = geojson,country=country, country_code = country_code, country_data = country_data, country_file = url_for('static', filename='TB_burden_countries_2020-10-08.csv'))

def query_samples(raw_queries,sample_links = True):
	neo4j_db = get_neo4j_db()
	queries = []
	tmp = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	admin_to_iso_a2 = {y["properties"]["admin"]:y["properties"]["iso_a2"] for y in tmp["features"]}

	for t in raw_queries:
		if t[0]=="country":
			queries.append("(%s)" %" OR ".join(["n.countryCode='%s'" % (admin_to_iso_a2[x].lower()) for x in t[1]]))
		else:
			if len([x for x in t[1] if x!=""])>0:
				queries.append("(%s)" %" OR ".join(["n.%s='%s'" % (t[0],x) for x in t[1]]))
	query = " AND ".join(queries)
	data = neo4j_db.read("MATCH (n:SRA ) WHERE %s RETURN n.id as id,n.country as country, n.countryCode as country_code, n.drtype as drtype,n.lineage as lineage,n.spoligotype as spoligotype" % query)
	if sample_links:
		for d in data:
			d["sample_link"] = '<a href="%s">%s</a>' % (url_for('results.run_result',sample_id=d["id"]),d["id"])
	return data

@bp.route('/sra/browse',methods=('GET', 'POST'))
def browse():
	neo4j_db = get_neo4j_db()
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
			data = query_samples(request.form.lists())
			geojson = get_geojson(Counter([x["country_code"].upper() for x in data]))
			# flash(geojson)
			print(list(request.form.lists()))
			return render_template('sra/browse.html', data = data , geojson=geojson, countries = country_list,lineages=lineages, query=json.dumps(list(request.form.lists())))

	return render_template('sra/browse.html', data = None, countries=country_list,lineages=lineages)
