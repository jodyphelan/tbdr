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
from .models import Result, Sample
from .db import db_session

def run_sample(uniq_id,sample_name,platform,f1,f2=None):
    # if current_user.is_authenticated:
    #     neo4j_db.write("CREATE (s:Sample:Private:Processing { id:'%s', sampleName:'%s', timestamp:'%s', userID:'%s'})" % (uniq_id,sample_name,datetime.now().isoformat(),current_user.id))
    # else:
    #     neo4j_db.write("CREATE (s:Sample:Processing { id:'%s', sampleName:'%s', timestamp:'%s'})" % (uniq_id,sample_name,datetime.now().isoformat()))
    # db.execute("INSERT INTO samples (id) VALUES ('%s')" % (uniq_id))
    # db.execute("INSERT INTO results (sample_id, status) VALUES ('%s', 'queueing')" % uniq_id)
    db_session.add(Sample(id=uniq_id))
    db_session.commit()
    db_session.add(Result(sample_id=uniq_id))
    db_session.commit()
    tbprofiler.delay(fq1=f1,fq2=f2,uniq_id=uniq_id,upload_dir=app.config["UPLOAD_FOLDER"],platform=platform,result_file_dir=app.config["APP_ROOT"]+url_for('static', filename='results'))



def sort_out_paried_files(upload_id,r1_suffix,r2_suffix):
    files = os.listdir(os.path.join(app.config["UPLOAD_FOLDER"],upload_id))
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
        sample_name = p if current_user.is_authenticated else uniq_id
        runs.append({"ID":uniq_id,"sample_name":sample_name,"R1":r1,"R2":r2})
    return runs

def sort_out_single_files(upload_id,r1_suffix):
    files = os.listdir(os.path.join(app.config["UPLOAD_FOLDER"],upload_id))
    prefixes = set()
    for f in files:
        tmp1 = re.search("(.+)%s" % r1_suffix,f)
        if tmp1==None:
            return "%s does not contain '_1.fastq.gz' as the file ending. Please revise your the file suffix in advanced options" % f
        prefixes.add(tmp1.group(1))
    runs = []
    for p in prefixes:
        uniq_id = str(uuid.uuid4())
        r1 = p + r1_suffix
        sample_name = p if current_user.is_authenticated else uniq_id
        runs.append({"ID":uniq_id,"sample_name":sample_name,"R1":r1,"R2":None})
    return runs

from .upload_forms import MultiFileUpload
@bp.route('/upload',methods=('GET', 'POST'))
def upload():
    form = MultiFileUpload()
    if request.method=="GET":
        upload_id = str(uuid.uuid4())
        session[upload_id] = "Pending"
        form.upload_id.data = upload_id
    if form.validate_on_submit():
        session[form.upload_id.data+"_form"] = json.dumps({"pairing":form.pairing.data,"platform":form.platform.data,"R1_suffix":form.forward_suffix.data,"R2_suffix":form.reverse_suffix.data})
        return redirect(url_for('upload.submit_runs',upload_id=form.upload_id.data))

    return render_template('upload/upload.html',form=form,upload_id=upload_id)

@bp.route('/submit_runs/<uuid:upload_id>',methods=('GET','POST'))
def submit_runs(upload_id):
    upload_id = str(upload_id)
    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"],upload_id)
    fd = json.loads(session[upload_id+"_form"])
    if fd['pairing']=="Paired":
        runs = sort_out_paried_files(upload_id, fd["R1_suffix"] ,fd["R2_suffix"])
    else:
        runs = sort_out_single_files(upload_id, fd["R1_suffix"])
    if isinstance(runs, str):
        flash(runs)
        return redirect(url_for('upload.upload'))
    print(runs)
    if session[upload_id]!="Submitted":
        for run in runs:
            r1 = "%s/%s" % (upload_dir,run["R1"])
            r2 = "%s/%s" % (upload_dir,run["R2"]) if run["R2"] else None
            run_sample(run["ID"],run["sample_name"],fd["platform"],r1,r2)
            
        session[upload_id] = "Submitted"
    else:
        print("Run already submitted")
    for run in runs:
        run["link"] = '<a href="'+url_for('results.run_result',sample_id=run["ID"])+'">'+run["ID"]+'</a>'
    return render_template('upload/upload_complete.html',runs=runs)
    

@bp.route('/file_upload/<uuid:upload_id>',methods=('GET','POST'))
def file_upload(upload_id):
    upload_id = str(upload_id)
    file = request.files['file']
    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"],upload_id)
    if upload_id in session:
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