"""Sign-up & log-in forms."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, PasswordField, SubmitField, SelectField, HiddenField
from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    Optional
)


class UploadForm(FlaskForm):
    """User Sign-up Form."""
    
    file1 = FileField(
        'File1',
        validators=[
            FileRequired(message="Need at least one file")
        ]
    )
    file2 = FileField(
        'File2',
    )
    platform  = SelectField(
        'Platform',
        choices=[
            ("Illumina","Illumina"),
            ("Nanopore","Nanopore")
        ],
        validators=[
            DataRequired(),
        ]
    )
    

    submit = SubmitField('Submit')

class AuthenicatedUploadForm(UploadForm):
    sample_name = StringField(
        'Name',
    )
    bedaquiline  = SelectField(
        'Bedaquiline',
        choices=[
            ("Not available","NA"),
            ("Resistant","R"),
            ("Sensitive","S")
        ],
    )
    delamanid  = SelectField(
        'Delamanid',
        choices=[
            ("Not available","NA"),
            ("Resistant","R"),
            ("Sensitive","S")
        ],
    )


class MultiFileUpload(FlaskForm):
    
    platform  = SelectField(
        'Platform',
        choices=[
            ("Illumina","Illumina"),
            ("Nanopore","Nanopore")
        ],
        validators=[
            DataRequired(),
        ]
    )
    pairing  = SelectField(
        'Pariring',
        choices=[
            ("Paired","Paired"),
            ("Single","Single")
        ],
        validators=[
            DataRequired(),
        ]
    )
    upload_id = HiddenField()
    forward_suffix = StringField(
        'Forward File Suffix',
    )
    reverse_suffix = StringField(
        'Reverse File Suffix',
    )
    submit = SubmitField('Submit')
