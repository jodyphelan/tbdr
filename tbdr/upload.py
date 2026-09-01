from pathlib import Path

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, Response, make_response, session
)
from werkzeug.exceptions import abort
import subprocess
#from aseantb.auth import login_required
from tbdr.worker import tbprofiler
import uuid
import os
from flask import current_app as app
import re
bp = Blueprint('upload', __name__)
from flask_login import current_user
import json
from .models import Result, Sample, Submission, SampleCollectionLink, Collection
from .db import db_session
import csv



def run_sample(uniq_id,sample_data,platform,f1,f2=None):
    valid_keys = {
        column.name
        for column in Sample.__table__.columns
    }
    sample_data = {
        key: value
        for key, value in sample_data.items()
        if key in valid_keys
    }

    db_session.add(Sample(id=uniq_id, **sample_data))
    db_session.commit()
    if app.config["SAMPLES_PUBLIC"]:
        collection = Collection.query.filter(Collection.name == "Public").first()
        if not collection:
            collection = Collection(name="Public", description="Public samples")
            db_session.add(collection)
            db_session.commit()
        db_session.add(SampleCollectionLink(sample_id=uniq_id, collection_id=collection.id))
        db_session.commit()
    db_session.add(Result(sample_id=uniq_id))
    db_session.commit()
    tbprofiler.delay(fq1=f1,fq2=f2,uniq_id=uniq_id,upload_dir=app.config["UPLOAD_FOLDER"],platform=platform,result_file_dir=app.config["APP_ROOT"]+url_for('static', filename='results'))


@bp.route('/check_for_samplesheet/<uuid:upload_id>',methods=('GET',))
def check_for_sample_sheet(upload_id):
    if os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"],str(upload_id),"sample_sheet.csv")):
        return make_response(("Sample sheet found", 200))
    else:
        return make_response(("Sample sheet not found", 404))


def sort_out_paried_files(upload_id,r1_suffix,r2_suffix):
    files = os.listdir(os.path.join(app.config["UPLOAD_FOLDER"],str(upload_id)))
    prefixes = set()
    for f in files:
        tmp1 = re.search("(.+)%s" % r1_suffix,f)
        tmp2 = re.search("(.+)%s" % r2_suffix,f)
        if tmp1==None and tmp2==None:
            return "%s does not contain '_1.fastq.gz' or '_2.fastq.gz' as the file ending. Please revise your the file suffix in advanced options" % f
        if tmp1:
            prefixes.add(tmp1.group(1))
        if tmp2:
            prefixes.add(tmp2.group(1))
    runs = []
    for p in prefixes:
        uniq_id = str(uuid.uuid4())
        r1 = p + r1_suffix
        r2 = p + r2_suffix
        if r1 not in files:
            return "%s is present in data file but not %s. Please check." % (r2,r1)
        if r2 not in files:
            return "%s is present in data file but not %s. Please check." % (r1,r2)
        sample_name =  uniq_id
        runs.append({"ID":uniq_id,"sample_name":sample_name,"R1":r1,"R2":r2})
    return runs

def sort_out_single_files(upload_id,r1_suffix):
    files = [f for f in os.listdir(os.path.join(app.config["UPLOAD_FOLDER"],upload_id)) if f.endswith(r1_suffix)]
    runs = []
    for f in files:
        print(f)
        uniq_id = str(uuid.uuid4())
        r1 = f 
        sample_name = uniq_id
        runs.append({"ID":uniq_id,"sample_name":sample_name,"R1":r1,"R2":None})
    return runs

from .upload_forms import MultiFileUpload
@bp.route('/upload',methods=('GET', 'POST'))
def upload():
    form = MultiFileUpload()
    if request.method=="GET":
        upload_id = str(uuid.uuid4())
        form.upload_id.data = upload_id
    if "result_id" in request.form: # navbar search
        return redirect(url_for('results.run_result',sample_id=request.form["result_id"]))
    if form.validate_on_submit():
        # session[form.upload_id.data+"_form"] = json.dumps({"pairing":form.pairing.data,"platform":form.platform.data,"R1_suffix":form.forward_suffix.data,"R2_suffix":form.reverse_suffix.data})
        # return redirect(url_for('upload.submit_runs',upload_id=form.upload_id.data))
        return submit_runs(form.upload_id.data)

    return render_template('upload/upload_alt.html',form=form,upload_id=upload_id)

@bp.route('/set_run_parameters/<uuid:upload_id>',methods=('POST',))
def set_run_parameters(upload_id):

    parameters = request.json

    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"],str(upload_id))
    with open(os.path.join(upload_dir,"run_parameters.json"), 'w') as f:
        json.dump(parameters, f)

    return make_response(("Run parameters saved successfully", 200))


@bp.route('/submit_runs/<uuid:upload_id>',methods=('GET','POST'))
def submit_runs(upload_id):
    upload_id = str(upload_id)
    
    if request.method=="POST":
        print("Submitting runs for upload ID:", upload_id)
        submission = db_session.query(Submission).filter(Submission.id==upload_id).first()
        if not submission:
            upload_dir = os.path.join(app.config["UPLOAD_FOLDER"],upload_id)
            # run_parameters = json.load(open(os.path.join(upload_dir,"run_parameters.json")))
            sample_sheet_file = os.path.join(upload_dir,"sample_sheet.csv") if os.path.exists(os.path.join(upload_dir,"sample_sheet.csv")) else os.path.join(upload_dir,"auto_sample_sheet.csv")
            sample_configuration = [row for row in csv.DictReader(open(sample_sheet_file))]
            for run in sample_configuration:
                run["unique_id"] = str(uuid.uuid4())
            for run in sample_configuration:
                r1 = "%s/%s" % (upload_dir,run["R1"])
                r2 = "%s/%s" % (upload_dir,run["R2"]) if run["R2"] else None
                run_sample(run["unique_id"],run,run["platform"],r1,r2)
            entry = Submission(id=upload_id,runs=sample_configuration)
            db_session.add(entry)
            db_session.commit()


    runs = db_session.query(Submission).filter(Submission.id==upload_id).first().runs
    for run in runs:
        run["link"] = '<a href="'+url_for('results.run_result',sample_id=run["unique_id"])+'">'+run["unique_id"]+'</a>'
    return render_template('upload/upload_complete.html',runs=runs)

def write_sample_sheet(upload_id):
    import fastq_files
    # samples = fastq_files.find_paired_fastq_samples(['/tmp/c2f7c70e-812e-4b20-9c78-f602c3081612'],r1_pattern='(.+)_1.fastq.gz', r2_pattern='(.+)_2.fastq.gz')
    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"],str(upload_id))
    form_data = json.load(open(os.path.join(upload_dir,"run_parameters.json")))
    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"],str(upload_id))

    pairing = form_data['pairing']
    
    if pairing=="Paired":
        r1_suffix = form_data["forward_suffix"]
        r2_suffix = form_data["reverse_suffix"]
        samples = fastq_files.find_paired_fastq_samples([upload_dir],r1_pattern='(.+)%s' % r1_suffix, r2_pattern='(.+)%s' % r2_suffix)
        
        samples = fastq_files.find_paired_fastq_samples([upload_dir],r1_pattern='(.+)%s' % form_data["forward_suffix"], r2_pattern='(.+)%s' % form_data["reverse_suffix"])
    else:
        samples = fastq_files.find_single_fastq_samples([upload_dir],r1_pattern='(.+)%s' % form_data["forward_suffix"])

    rows = []
    for s in samples:
        row = {
            "sample_name": s.prefix,
            "platform": form_data.get("platform"),
            "layout": form_data.get("pairing"),
            "R1": s.r1[0].split("/")[-1] if s.r1 else None,
            "R2": s.r2[0].split("/")[-1] if hasattr(s, "r2") and s.r2 else None
        }
        rows.append(row)
    sample_sheet_path = os.path.join(upload_dir,"auto_sample_sheet.csv")
    with open(sample_sheet_path, 'w', newline='') as csvfile:
        fieldnames = rows[0].keys() 
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def is_empty(value):
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False

def validate_sample_sheet(upload_id):
    upload_dir = Path(app.config["UPLOAD_FOLDER"]) / upload_id
    sample_sheet_path = upload_dir / "sample_sheet.csv"
    if not sample_sheet_path.exists():
        sample_sheet_path = upload_dir / "auto_sample_sheet.csv"
    if not sample_sheet_path.exists():
        raise FileNotFoundError(f"Sample sheet not found at {sample_sheet_path}")
    with open(sample_sheet_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        required_fields = ["sample_name", "platform", "layout", "R1"]
        for field in required_fields:
            if field not in reader.fieldnames:
                raise ValueError(f"Sample sheet is missing required column: {field}")
        for row in reader:
            if is_empty(row["sample_name"]) or is_empty(row["R1"]):
                raise ValueError(f"Sample sheet row is missing required data: {row}")
            if row["layout"] == "paired" and is_empty(row.get("R2")):
                raise ValueError(f"Sample sheet row is missing R2 for paired layout: {row}")
            r1_file = upload_dir / row["R1"]
            if not r1_file.exists():
                raise FileNotFoundError(f"R1 file not found: {row["R1"]}")
            if not is_empty(row.get("R2")):
                r2_file = upload_dir / row["R2"]
                if not r2_file.exists():
                    raise FileNotFoundError(f"R2 file not found: {row["R2"]}")

@bp.route('/get_sample_configuration/<upload_id>',methods=('GET',))
def get_sample_configuration(upload_id):
    upload_dir = Path(app.config["UPLOAD_FOLDER"]) / str(upload_id)
    sample_sheet_path = upload_dir / "sample_sheet.csv"
    auto_sample_sheet_path = upload_dir / "auto_sample_sheet.csv"
    if not sample_sheet_path.exists():
        try:
            write_sample_sheet(upload_id)
            validate_sample_sheet(upload_id)
        except Exception as e:
            print(f"Error generating or validating sample sheet: {str(e)}")
            return make_response((f"Error generating sample sheet: {str(e)}", 500))
    else:
        try:
            validate_sample_sheet(upload_id)
        except Exception as e:
            print(f"Error validating sample sheet: {str(e)}")
            return make_response((f"Error validating sample sheet: {str(e)}", 500))
    chosen_sample_sheet_path = sample_sheet_path if sample_sheet_path.exists() else auto_sample_sheet_path
    with open(chosen_sample_sheet_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = [row for row in reader]
    print(rows)
    return make_response((json.dumps(rows), 200, {'Content-Type': 'application/json'}))

@bp.route('/parse_sample_sheet/<uuid:upload_id>',methods=('GET','POST'))
def parse_sample_sheet(upload_id):
    upload_id = str(upload_id)
    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"],upload_id)
    sample_sheet_path = os.path.join(upload_dir,"sample_sheet.csv")
    # Implement the logic for parsing the sample sheet here
    if os.path.exists(sample_sheet_path):
        print(f"Parsing sample sheet at {sample_sheet_path}")
        rows = []
        reader = csv.DictReader(open(sample_sheet_path))
        header_fields = ["R1", "R2", "sample_name"]
        # validate header fields
        missing_fields = [field for field in header_fields if field not in reader.fieldnames]
        if missing_fields:
            return make_response((f"Sample sheet is missing required columns: {', '.join(missing_fields)}", 400))

        for row in csv.DictReader(open(sample_sheet_path)):
            print(row)
            if "R1" not in row or "R2" not in row:
                return make_response(("Sample sheet must contain 'R1' and 'R2' columns", 400))
            r1=row['R1']
            r2=row['R2'] if row["R2"]!="" else None
            if r1 and not os.path.exists(os.path.join(upload_dir,r1)):
                return make_response(("R1 file %s not found in upload directory" % r1, 400))
            if r2 and not os.path.exists(os.path.join(upload_dir,r2)):
                return make_response(("R2 file %s not found in upload directory" % r2, 400))
            rows.append(row)

        
        return make_response(("Sample sheet parsed successfully", 200))
    else:
        return make_response(("Sample sheet not found", 404))
    

@bp.route('/file_upload/<uuid:upload_id>',methods=('GET','POST'))
def file_upload(upload_id):
    upload_id = str(upload_id)
    file = request.files['file']
    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"],upload_id)
    
    if not os.path.isdir(upload_dir):
        os.mkdir(upload_dir)
    save_path = os.path.join(upload_dir, file.filename)
    current_chunk = int(request.form['dzchunkindex'])
    # If the file already exists it's ok if we are appending to it,
    # but not if it's new file that would overwrite the existing one
    if os.path.exists(save_path) and current_chunk == 0:
        # 400 and 500s will tell dropzone that an error occurred and show an error
        return make_response(('File already exists', 400))
    try:
        with open(save_path, 'ab') as f:
            f.seek(int(request.form['dzchunkbyteoffset']))
            f.write(file.stream.read())
    except OSError:
        # log.exception will include the traceback so we can see what's wrong 
        # log.exception('Could not write to file')
        return make_response(("Not sure why,"
                              " but we couldn't write the file to disk", 500))
    total_chunks = int(request.form['dztotalchunkcount'])
    if current_chunk + 1 == total_chunks:
        # This was the last chunk, the file should be complete and the size we expect
        if os.path.getsize(save_path) != int(request.form['dztotalfilesize']):
            return make_response(('Size mismatch', 500))
        else:
            print(f'File {file.filename} has been uploaded successfully from session {upload_id} to {save_path}')
    else:
        print(f'Chunk {current_chunk + 1} of {total_chunks} for file {file.filename} complete')
    return make_response(("Chunk upload successful", 200))
