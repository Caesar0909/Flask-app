from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from wtforms import ValidationError
from ..models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1, 64), Email()], description='email', id='email')
    password = PasswordField('Password', validators = [Required()], description = 'password')
    submit = SubmitField('Login')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first() is None:
            raise ValidationError("This email does not exist in our system. If you think we are wrong, please contact us.")

class EmailResetForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1, 64), Email()], description='email')

    def validate_email(self, field):
        """Check to make sure the email is actually in the system
        """
        if User.query.filter_by(email=field.data).first() is None:
            raise ValidationError("This email does not exist in our system. Please contact an admin if you think we are wrong!")

class PasswordResetForm(FlaskForm):
    password = PasswordField('Password', validators=[Required(), EqualTo('password2', message="Passwords must match.")],
                                    description='password')
    password2 = PasswordField('Confirm Password', validators=[Required()], description='re-enter password')
    submit = SubmitField('Register')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1, 64), Email()], description='email')
    username = StringField('Username', validators=[Required(), Length(1, 64), Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                            'Usernames must have only letters, numbers, dots, or underscores')],
                            description='username')
    password = PasswordField('Password', validators=[Required(), EqualTo('password2', message="Passwords must match.")],
                                    description='password')
    password2 = PasswordField('Confirm Password', validators=[Required()], description='re-enter password')
    submit = SubmitField('Register')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('This email is already registered.')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('This username is already in use. Please choose another.')
