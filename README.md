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
celery -A tbdr.worker worker --loglevel=info --concurrency=1
```
