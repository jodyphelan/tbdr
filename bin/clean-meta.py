import csv
import ena_query.country
import ena_query.dates
import argparse
parser = argparse.ArgumentParser(description='Clean metadata CSV',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--input',type=str,help='Input CSV file',required=True)
parser.add_argument('--output',type=str,help='Output CSV file',required=True)
args = parser.parse_args()
meta = {}

for row in csv.DictReader(open(args.input,encoding='utf-8-sig')):
    country = ena_query.country.clean_country(row['country'])
    meta_row = {
        'id': row['id'],
        'country': country,
        'iso_a3': ena_query.country.country2iso3(country),
        'year_of_collection': ena_query.dates.clean_date(row['date']),
    }
    meta[meta_row['id']] = meta_row

with open(args.output, 'w') as csvfile:
    fieldnames = ['id', 'country', 'iso_a3', 'year_of_collection']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for row in meta.values():
        writer.writerow(row)