"""Connect to postgresql database and get all the unique values of the column 'iso_a3' from the table 'samples'"""
import psycopg2
import sys
import json
from  ena_query.query import get_ena_country
from tqdm import tqdm


geojson = json.load(open("tbdr/static/custom.geo.json"))

iso2_to_iso3 = {}
for f in geojson["features"]:
    iso2 = f["properties"]["iso_a2"].lower()
    iso3 = f["properties"]["iso_a3"].lower()
    iso2_to_iso3[iso2] = iso3

db = psycopg2.connect(
    dbname='tbdr',
    user="",
    password=""
)
c = db.cursor()

# get all the unisue values of the column 'iso_a3' from the table 'samples'
c.execute("SELECT DISTINCT iso_a3 FROM samples")
iso_a3 = c.fetchall()
print(iso_a3)

for i in tqdm(iso_a3, desc="Updating iso_a3"):
    iso_a2 = i[0]
    iso_a3 = iso2_to_iso3.get(iso_a2, None)
    if iso_a3 is None:
        print(f"Could not find iso_a3 for iso_a2: {iso_a2}")
    else:
        print(f"Setting {iso_a2} -> {iso_a3}")
    # update entries in the table 'samples' with the correct iso_a3 values
        cmd = f"UPDATE samples SET iso_a3 = '{iso_a3}' WHERE iso_a3 = '{iso_a2}'"
        print(cmd)
        c.execute(cmd)
        db.commit()

c.execute("SELECT id FROM samples")
rows = c.fetchall()
for row in tqdm(rows, desc="Updating iso_a3 for samples"):
    id = row[0]
    print(f"Updating {id}")
    # get iso_a3 value for the sample
    c.execute(f"SELECT iso_a3 FROM samples WHERE id = '{id}'")
    iso_a3 = c.fetchone()[0]
    if iso_a3 is None:
        try:
            data = get_ena_country(id)
            if data['iso3'] is not None:
                iso_a3 = data['iso3'].lower()
                cmd = f"UPDATE samples SET iso_a3 = '{iso_a3}' WHERE id = '{id}'"
                print(cmd)
                c.execute(cmd)
                db.commit()
        except:
            pass

