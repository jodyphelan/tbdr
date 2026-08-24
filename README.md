# tb-profiler-webserver

This repository hosts the code to deploy a webserver to wrap around the function of [TB-Profiler](https://github.com/jodyphelan/TBProfiler/). Updates will follow soon!

## Installation
Installation requires tb-profiler, flask, celery and redis.
To run it on your local machine:
```
# Install libraries
conda install python=3.7 flask redis celery statsmodels bwa samtools=1.10 bcftools=1.10 parallel freebayes>=1.3.5 gatk4 bedtools samclip delly=0.8.7 snpEff plotly weasyprint
pip install neo4j redis tqdm requests flask_sqlalchemy flask_login flask_session flask_wtf email_validator

python setup.py install

# Run flask
export FLASK_APP=tbdr
export FLASK_ENV=development
flask run

# Run rabbit-mq server
rabbitmq-server

# Run celery
celery -A tbdr.celery_app:celery worker --loglevel=info --concurrency=1
```

## Docker Compose deployment

The repository includes a Compose deployment for a single host. It runs the
tbdr web server and Celery worker from one `linux/amd64` image, with
PostgreSQL and Redis as separate services. The supplied `who_v3` database is
embedded in the image.

New uploads inherit the global `UPLOADED_SAMPLES_PUBLIC` setting. Leave it as
`false` to keep new samples out of the public SRA views, or set it to `true`
to include new samples in those views. This setting affects new uploads only;
existing samples retain their stored visibility. Private samples are not
access-controlled by result ID.

Docker Desktop on Apple Silicon can run the image through its amd64
emulation. Bioinformatics jobs are CPU- and memory-intensive; the defaults
use two TB-Profiler threads, 8 GB per job, and one Celery job at a time.

```sh
cp .env.example .env
# Edit .env and set POSTGRES_PASSWORD and TBDR_SECRET_KEY.
docker compose up --build -d
```

The web interface is available at <http://localhost:8000>. Follow startup and
analysis logs with:

```sh
docker compose logs -f web worker
```

PostgreSQL data, uploaded reads, generated reports, and Redis state are stored
in named volumes. To stop the services while retaining data, run
`docker compose down`; do not use `docker compose down -v` unless those data
volumes are intentionally being deleted. Back up the PostgreSQL volume with
`docker compose exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"`.
