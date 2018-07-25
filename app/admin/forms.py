from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FileField
from wtforms import DecimalField, RadioField, SelectField
from wtforms.ext.sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField
from wtforms.validators import Required, Length, Email, Optional
from wtforms import widgets
from wtforms.widgets import html_params
from wtforms import ValidationError
from flask_pagedown.fields import PageDownField
import pytz
import pycountry

from ..models import Role, Instrument, User, Group, Model

def role_choice():
    return Role.query

def owner_choice():
    return User.query

def group_choice():
    return Group.query

def device_choice():
    return Instrument.query

def model_choice():
    return Model.query

def select_multi_checkbox(field, ul_class='', **kwargs):
    kwargs.setdefault('type', 'checkbox')
    field_id = kwargs.pop('id', field.id)
    html = [u'<ul %s>' % html_params(id=field_id, class_=ul_class)]
    for value, label, checked in field.iter_choices():
        choice_id = u'%s-%s' % (field_id, value)
        options = dict(kwargs, name=field.name, value=value, id=choice_id)
        if checked:
            options['checked'] = 'checked'
        html.append(u'<li><input %s /> ' % html_params(**options))
        html.append(u'<label for="%s">%s</label></li>' % (field_id, label))
    html.append(u'</ul>')
    return u''.join(html)

tz_options  = zip(pytz.common_timezones, pytz.common_timezones)
iso_options = [(c.alpha_2, c.name) for c in pycountry.countries]

model_options = [
    ('E-BAM', 'E-BAM'),
    ('MetOne Neighborhood Monitor', 'MetOne Neighborhood Monitor'),
    ('2BTech Model 202', '2BTech Model 202'),
    ('MIT2016', 'MIT-2016'),
    ('TREX', 'TREX'),
    ('Thermo 43i', 'Thermo 43i'),
    ('TrexPM', 'TREX PM')
    ]

type_options = [
    ('mit', 'MIT-2016'),
    ('ebam', 'E-BAM'),
    ('trex', 'TREX2017'),
    ('orphan', 'Other/Orphan'),
    ('trex_pm', 'TREX PM'),
    ('other', 'Other')
    ]

loglevel_options = ["INFO", "ERROR", "WARNING", "CRITICAL"]

class DeviceForm(FlaskForm):
    sn              = StringField('Serial Number', validators=[Required(), Length(3, 24)])
    model           = SelectField('Model', choices=model_options)
    discriminator   = SelectField('Class', choices=type_options)
    particle_id     = StringField('Particle Device ID', validators=[Optional(), Length(5, 24)])
    location        = StringField('Location', validators=[Optional()])
    city            = StringField('City', validators=[Optional()])
    group           = QuerySelectField('Group', query_factory=group_choice, allow_blank=True)
    country         = SelectField('Country', choices=iso_options, default='US')
    timezone        = SelectField('Timezone', choices=list(tz_options), default='US/Eastern')
    owner           = QuerySelectField('Device Owner', query_factory=owner_choice, allow_blank=True)
    outdoors        = BooleanField('Outdoors', validators=[Optional()])
    description     = PageDownField('Description', validators=[Optional()])
    latitude        = StringField('Latitude', validators=[Optional()])
    longitude       = StringField('Longitude', validators=[Optional()])

    def unique_sn(self, sn):
        """Check to make sure the sn is not already in use
        """
        if Instrument.query.filter_by(sn=sn).first() is not None:
            self.sn.errors.append('This sn already exists in our system. Please try a different SN')

            return False


class UserForm(FlaskForm):
    email       = StringField('Email', validators = [Required(), Length(1, 64), Email()])
    username    = StringField('Username', validators = [Required()])
    confirmed   = BooleanField('Confirmed', default = False)
    role        = QuerySelectField('Role', query_factory = role_choice)
    groups      = QuerySelectMultipleField('Groups',
                    query_factory = group_choice)


class FileUploadForm(FlaskForm):
    file        = FileField('File')
    device      = QuerySelectField('Device', query_factory=device_choice)


class ModelUploadForm(FlaskForm):
    file        = FileField('Model File', validators=[Required()])
    label       = StringField('Label', validators=[Required()])
    description = PageDownField('Description', validators=[Optional()])
    rmse        = DecimalField('RMSE', validators=[Optional()])
    mae         = DecimalField('MAE', validators=[Optional()])
    r2          = DecimalField('R2', validators=[Optional()])

class LogForm(FlaskForm):
    message = PageDownField("Message", validators=[Required()])
    level = SelectField("Level", choices=list(zip(loglevel_options, loglevel_options)), default='INFO')
    instrument = QuerySelectField("Instrument", query_factory=device_choice, get_label='sn', get_pk=lambda x: x.sn)
