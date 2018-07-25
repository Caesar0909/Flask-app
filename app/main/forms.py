from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from wtforms import ValidationError
from ..models import User, Credentials

class ResetForm(FlaskForm):
    email          = StringField('Email', validators = [Required(), Length(1, 64), Email()])
    password       = PasswordField('Password', validators = [Required()])
    token          = StringField('2FA Token', validators = [Required()])
    submit         = SubmitField('Log In')

class TokenForm(FlaskForm):
    name    = StringField('Token Name', validators = [Required()], description = 'Enter Token Name')
    submit  = SubmitField('Generate Token')

class UserSettingsForm(FlaskForm):
    username        = StringField('Username', validators = [Required(), Length(1, 64), Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                                    'Usernames must have only letters, numbers, dots, or underscores')],
                                    description = 'username')
    old_password    = PasswordField('Old Password', validators = [Required()], description = 'old password')
    password        = PasswordField('New Password', validators = [EqualTo('password2', message = "Passwords must match.")],
                                    description = 'password')
    password2       = PasswordField('Confirm Password', description = 're-enter password')
