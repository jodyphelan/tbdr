import argparse
from tbdr import create_app
from flask import url_for

argparser = argparse.ArgumentParser()
argparser.add_argument("-1", "--R1", help="Path to first fastq file",required = True)
argparser.add_argument("-2", "--R2", help="Path to second fastq file",required = True)
argparser.add_argument("--uniq_id", help="Unique ID for the sample",required = True)
argparser.add_argument("--platform",choices = ['illumina','nanopore'], help="Unique ID for the sample",required = True)
argparser.add_argument("--dir", help="Unique ID for the sample",required = True)

args = argparser.parse_args()

app = create_app()

from tbdr.worker import tbprofiler
tbprofiler.delay(
    fq1=args.R1,
    fq2=args.R2,
    uniq_id=args.uniq_id,
    upload_dir=app.config["UPLOAD_FOLDER"],
    platform=args.platform,
    result_file_dir=args.dir
)