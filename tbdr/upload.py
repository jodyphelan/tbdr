from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, Response, make_response, session
)
from werkzeug.exceptions import abort
import subprocess
#from aseantb.auth import login_required
from tbdr.db import  get_neo4j_db
from tbdr.worker import tbprofiler
import uuid
from werkzeug.utils import secure_filename
import os
from flask import current_app as app
from tbdr.utils import get_fastq_md5
import re
from datetime import datetime
bp = Blueprint('upload', __name__)
from flask_login import current_user
import shutil
import json

def run_sample(uniq_id,sample_name,platform,f1,f2=None,neo4j_db=None):
    if current_user.is_authenticated:
        neo4j_db.write("CREATE (s:Sample:Private:Processing { id:'%s', sampleName:'%s', timestamp:'%s', userID:'%s'})" % (uniq_id,sample_name,datetime.now().isoformat(),current_user.id))
    else:
        neo4j_db.write("CREATE (s:Sample:Processing { id:'%s', sampleName:'%s', timestamp:'%s'})" % (uniq_id,sample_name,datetime.now().isoformat()))
    tbprofiler.delay(fq1=f1,fq2=f2,uniq_id=uniq_id,storage_dir=app.config["UPLOAD_FOLDER"],platform=platform,result_file_dir=app.config["APP_ROOT"]+url_for('static', filename='results'))

# @bp.route('/upload',methods=('GET', 'POST'))
# def upload():
#     print(vars(current_user))
#     neo4j_db = get_neo4j_db()
#     if request.method == 'POST':
#         error=None
#         if "single_sample_submit" in request.form:
#             platform=request.form["platform"]
#             uniq_id = str(uuid.uuid4())
#             if "sample_name" in request.form:
#                 sample_name = request.form["sample_name"] if request.form["sample_name"]!="" else uniq_id
#             else:
#                 sample_name = uniq_id
#             if request.files['file1'].filename=="":
#                 error = "No file found for read 1, please try again!"
#             if error==None:
#                 run_sample(uniq_id,sample_name,platform,request.files['file1'],request.files.get("file2",None), neo4j_db = neo4j_db)
#                 return redirect(url_for('results.run_result', sample_id=uniq_id))
#         elif "multi_sample_submit" in request.form:
#             if request.form["r1_suffix"]!="" and request.form["r2_suffix"]!="":
#                 print("Setting suffix")
#                 r1_suffix = request.form["r1_suffix"].strip()
#                 r2_suffix = request.form["r2_suffix"].strip()
#             elif request.form["r1_suffix"]=="" and request.form["r2_suffix"]=="":
#                 r1_suffix = "_1.fastq.gz"
#                 r2_suffix = "_2.fastq.gz"
#             else:
#                 error = "If you would like to change the file suffix please fill in for both the forward and reverse"
#             if error==None:
#                 files = {f.filename:f for f in list(request.files.lists())[0][1]}
#                 if len(files)%2!=0:
#                     error = "Odd number of files. There should be two files per sample, please check."
#             if error==None:
#                 prefixes = set()
#                 for f in files.keys():
#                     tmp1 = re.search("(.+)%s" % r1_suffix,f)
#                     tmp2 = re.search("(.+)%s" % r2_suffix,f)
#                     if tmp1==None and tmp2==None:
#                         error = "%s does not contain '_1.fastq.gz' or '_2.fastq.gz' as the file ending. Please revise your file names" % f
#                         break
#                     if tmp1:
#                         prefixes.add(tmp1.group(1))
#                     if tmp2:
#                         prefixes.add(tmp2.group(1))
#             if error==None:
#                 runs = []
#                 for p in prefixes:
#                     uniq_id = str(uuid.uuid4())
#                     r1 = p + r1_suffix
#                     r2 = p + r2_suffix
#                     if r1 not in files:
#                         error = "%s is present in data file but not %s. Please check." % (r2,r1)
#                     if r2 not in files:
#                         error = "%s is present in data file but not %s. Please check." % (r1,r2)
#                     sample_name = p if g.user else uniq_id
#                     runs.append({"ID":uniq_id,"sample_name":sample_name,"R1":r1,"R2":r2})
#             if error==None:
#                 csv_text = "ID,Name,R1,R2\n" + "\n".join(["%(ID)s,%(sample_name)s,%(R1)s,%(R2)s" % d for d in runs])
#                 for run in runs:
#                     run_sample(db,username,run["ID"],run["sample_name"],request.form["platform"],files[run["R1"]],files[run["R2"]])

#                 return Response(csv_text,mimetype="text/csv",headers={"Content-disposition": "attachment; filename=tb-profiler-IDs.csv"})

#         flash(error)
#     return render_template('upload/upload.html')


def sort_out_files(upload_id,r1_suffix,r2_suffix):
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


from .upload_forms import UploadForm, AuthenicatedUploadForm, MultiFileUpload
@bp.route('/upload',methods=('GET', 'POST'))
def upload():
    neo4j_db = get_neo4j_db()
    form = MultiFileUpload()
    if request.method=="GET":
        upload_id = str(uuid.uuid4())
        session[upload_id] = "Pending"
        form.upload_id.data = upload_id
    flash(form.errors)
    if form.validate_on_submit():
        files = os.listdir(session.get('upload_dir'))
        session[form.upload_id.data+"_form"] = json.dumps({"platform":form.platform.data,"R1_suffix":form.forward_suffix.data,"R2_suffix":form.reverse_suffix.data})
        return redirect(url_for('upload.submit_runs',upload_id=form.upload_id.data))

    flash(form.errors)
    return render_template('upload/upload.html',form=form,upload_id=upload_id)

@bp.route('/submit_runs/<uuid:upload_id>',methods=('GET','POST'))
def submit_runs(upload_id):
    upload_id = str(upload_id)
    neo4j_db = get_neo4j_db()
    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"],upload_id)
    fd = json.loads(session[upload_id+"_form"])
    runs = sort_out_files(upload_id, fd["R1_suffix"] ,fd["R2_suffix"])
    if isinstance(runs, str):
        flash(runs)
        return redirect(url_for('upload.upload'))
    print(runs)
    if session[upload_id]!="Submitted":
        for run in runs:
            r1 = "%s/%s" % (upload_dir,run["R1"])
            r2 = "%s/%s" % (upload_dir,run["R2"])
            run_sample(run["ID"],run["sample_name"],fd["platform"],r1,r2,neo4j_db)
            
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