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


class MetaForm(FlaskForm):
    """User Sign-up Form."""
    
    file1 = FileField(
        'File1',
        validators=[
            FileRequired(message="Need at least one file")
        ]
    )
    submit = SubmitField('Submit')
