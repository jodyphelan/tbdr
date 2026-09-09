from flask import (
	Blueprint, redirect,  render_template, request, url_for, Response
)
import json
# from tbdr.auth import login_required
from flask import current_app as app
from collections import Counter
bp = Blueprint('sra', __name__)
import sys
import csv
import os
from .db import db_session
from sqlalchemy import text

def get_geojson(country_counts):
	print(country_counts)
	raw_geojson = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	geojson = {"type":"FeatureCollection", "features":[]}

	for f in raw_geojson["features"]:
		country = f["properties"]["iso_a3"].upper()

		if country in country_counts:
			f["properties"]["num_isolates"] = country_counts[country]
			geojson["features"].append(f)

	print(geojson)
	return geojson

def get_sample_data(collection_id):
	query = """
				WITH collection_samples AS (
					SELECT s.*
					FROM samples s
					JOIN sample_collection_link scl
						ON scl.sample_id = s.id
					JOIN collections c
						ON c.id = scl.collection_id
					WHERE c.name = '%s'
				)
				SELECT 'iso_a3' AS field, iso_a3 AS value, COUNT(*) AS count
				FROM collection_samples
				GROUP BY iso_a3

				UNION ALL

				SELECT 'year_of_collection', year_of_collection::text, COUNT(*)
				FROM collection_samples
				GROUP BY year_of_collection

				UNION ALL

				SELECT 'drtype', drtype, COUNT(*)
				FROM collection_samples
				GROUP BY drtype

				UNION ALL

				SELECT 'lineage', lineage, COUNT(*)
				FROM collection_samples
				GROUP BY lineage

				ORDER BY field, count DESC;
	""" % (collection_id)
	return db_session.execute(text(query)).fetchall()

@bp.route('/get_colection_size/<collection_name>',methods=('GET',))
def get_collection_size(collection_name):
	query = """
				SELECT COUNT(*) from sample_collection_link 
				WHERE collection_id IN (
					SELECT id FROM collections WHERE collections.name = '%s'
				)
			""" % collection_name
	data = db_session.execute(text(query)).fetchall()
	print(data)

@bp.route('/sra',methods=('GET', 'POST'))
def sra():
	if request.method == 'POST':
		if "result_id" in request.form: # navbar search
			return redirect(url_for('results.run_result',sample_id=request.form["result_id"]))
	
	sample_data = get_sample_data("public")

	print(sample_data)
	country_counts = {row[1]: row[2] for row in sample_data if row[0]=="iso_a3" and row[1] is not None}
	dr_counts = {row[1]: row[2] for row in sample_data if row[0]=="drtype" and row[1] is not None}
	lineage_counts = [{'lineage': row[1], 'count': row[2]} for row in sample_data if row[0]=="lineage" and row[1] is not None]
	year_of_collection = [{'year': int(row[1]), 'count': row[2]} for row in sample_data if row[0]=="year_of_collection" and row[1] is not None]
	dr_order = {"Susceptible":1,"RR-TB":2,"HR-TB":3,"MDR-TB":4,"Pre-XDR-TB":5,"XDR-TB":6,"Other":7}
	dr_data = {d:dict(dr_counts).get(d,0) for d in dr_order}
	total_samples = sum(dr_counts.values())

	
	raw_geojson = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	geojson = {"type":"FeatureCollection", "features":[]}

	for f in raw_geojson["features"]:
		country = f["properties"]["iso_a3"].upper()


		if country in country_counts:
			f["properties"]["num_isolates"] = country_counts[country]
			geojson["features"].append(f)






	return render_template('sra/landing.html', total_samples=total_samples,dr_data=dr_data, geojson=geojson, top_mutations = None, lineage_counts=lineage_counts,year_of_collection=year_of_collection)

@bp.route('/sra/country')
def country():
	return "Add country to see country data"

@bp.route('/sra/country/<country>')
def country_data(country):
	data = query_samples([("country",[country])])
	country_code = data[0]["country_code"].upper()
	print(country_code)
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
	admin_to_iso_a3 = {y["properties"]["admin"]:y["properties"]["iso_a3"].upper() for y in tmp["features"]}

	for t in raw_queries:
		if t[0]=="country":
			queries.append("(%s)" %" OR ".join(["iso_a3='%s'" % (admin_to_iso_a3[x].upper()) for x in t[1]]))
		else:
			if len([x for x in t[1] if x!=""])>0:
				queries.append("(%s)" %" OR ".join(["%s='%s'" % (t[0],x) for x in t[1]]))
	where_query = "WHERE "+" AND ".join(queries) if len(queries)>0 else ""
	query = "SELECT id, iso_a3 as country_code, drtype, lineage, year_of_collection FROM SAMPLES %s AND public = true" % where_query
	query = """
				SELECT
					s.id,
					s.iso_a3 AS country_code,
					s.drtype,
					s.lineage,
					s.year_of_collection
				FROM samples s
				JOIN sample_collection_link scl
					ON scl.sample_id = s.id
				JOIN collections c
					ON c.id = scl.collection_id
				%s
				AND c.name = 'public'
			""" % where_query
	print(query)
	data = db_session.execute(text(query)).fetchall()

	data = [x._asdict() for x in data]
	if sample_links:
		for d in data:
			d["sample_link"] = '<a href="%s">%s</a>' % (url_for('results.run_result',sample_id=d["id"]),d["id"])
	return data

@bp.route('/sra/browse',methods=('GET', 'POST'))
def browse():
	tmp = json.load(open(app.config["APP_ROOT"]+url_for('static', filename='custom.geo.json')))
	country_list = sorted([y["properties"]["admin"] for y in tmp["features"]])
	barcode_bed = os.path.join(app.config['TB_PROFILER_DB_DIR'], app.config['TB_PROFILER_DB'], 'barcode.bed')
	lineages = sorted(list(set([l.strip().split()[3] for l in open(barcode_bed)])))
	if request.method == 'POST':
		if "result_id" in request.form: # navbar search
					return redirect(url_for('results.run_result',sample_id=request.form["result_id"]))
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
			dr_data = dict(Counter([x["drtype"] for x in data if x["drtype"]]))
			lineage_counts = [{"lineage": k, "count": v} for k,v in Counter([x["lineage"] for x in data if x["lineage"]]).items()]
			print(lineage_counts)
			print(data)
			year_of_collection = [{"year": k, "count": v} for k,v in Counter([x["year_of_collection"] for x in data if x.get("year_of_collection")]).items()]
			print(year_of_collection)
			return render_template('sra/browse.html', data = data , dr_data = dr_data,geojson=geojson, year_of_collection=year_of_collection,lineage_counts=lineage_counts,countries = country_list,lineages=lineages, query=json.dumps(list(request.form.lists())))

	return render_template('sra/browse.html', data = None, countries=country_list,lineages=lineages)
