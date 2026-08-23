import argparse
from sqlalchemy import create_engine, text


argparser = argparse.ArgumentParser()
argparser.add_argument("--user", help="Database user",required = True)
argparser.add_argument("--password", help="Database password",required = True)

args = argparser.parse_args()



engine = create_engine(f'postgresql+psycopg2://{args.user}:{args.password}@localhost/tbdr')

# perform select * from submissions;
with engine.connect() as connection:
    result = connection.execute(text("select * from submissions"))
    for row in result:
        for run in row[1]:
            rid = run['ID']
            status = connection.execute(text(f"select status from results WHERE sample_id = '{rid}';")).fetchone()[0]
            print(row[0],rid,status,sep="\t")
