from flask import render_template, redirect, request, url_for, flash, session, abort, current_app
from flask_login import login_user, logout_user, login_required, current_user
from . import auth
#import pyqrcode
from ..models import User, Group
from .. import db
from io import StringIO, BytesIO
from .forms import LoginForm, RegistrationForm, EmailResetForm, PasswordResetForm
from .helpers import confirmation_email, password_reset_email
import sendgrid

@auth.route('/send-confirmation')
@login_required
def resend_confirmation():
	token = current_user.generate_confirmation_token()

	# send a confirmation email
	if current_app.config['EMAILS']: #pragma: no cover
		sender = sendgrid.SendGridAPIClient(apikey=current_app.config['SENDGRID_API_KEY'])

		email = confirmation_email(
					to_email=current_user.email,
					from_email=current_app.config['FROM_EMAIL'],
					from_name=current_app.config['FROM_NAME'],
					link=url_for('auth.confirm', token=token, _external=True))

		response = sender.client.mail.send.post(request_body=email)

	flash("A confirmation email has been sent to your email address of record.", 'success')

	return redirect(url_for('main.index'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
	if current_user.is_authenticated:
		return redirect(url_for('main.index'))

	form = LoginForm()

	if request.method == 'POST' and form.validate_on_submit():
		user = User.query.filter_by(email=form.email.data).first()

		if user is None or not user.verify_password(form.password.data):
			# Raise an error
			form.password.errors.append('Invalid password.')

			return render_template('auth/login.html', form=form)

		login_user(user, True)

		# Set the users last_seen field
		user.ping()

		return redirect(request.args.get('next') or url_for('main.user_portal'))

	return render_template('auth/login.html', form=form)

@auth.route('/reset-pswd', methods=['GET', 'POST'])
def forgot_password():
	if current_user.is_authenticated:
		return redirect( url_for('main.index') )

	form = EmailResetForm()

	if request.method == 'POST' and form.validate_on_submit():
		user = User.query.filter_by(email=form.email.data).first()

		# Generate the token
		token = user.generate_confirmation_token()

		# send a confirmation email
		if current_app.config['EMAILS']: #pragma: no cover
			sender = sendgrid.SendGridAPIClient(apikey=current_app.config['SENDGRID_API_KEY'])

			email  = password_reset_email(
							to_email=user.email,
							from_email=current_app.config['FROM_EMAIL'],
							from_name=current_app.config['FROM_NAME'],
							link=url_for('auth.confirm_reset',
											token=token,
											username=user.username,
											_external=True))

			response = sender.client.mail.send.post(request_body=email)

		# Render a thank you for registering message!
		flash("Thanks! You should receive an email shortly with furthur instructions.", 'info')

		return redirect( url_for('main.index') )

	return render_template('auth/reset-form.html', form=form)

@auth.route('/reset-form', methods=['GET', 'POST'])
def confirm_reset():
	token = request.args.get('token')
	username = request.args.get('username')

	user = User.query.filter_by(username=username).first_or_404()

	form = PasswordResetForm()

	# Return a password reset form which when completed correctly, returns you to logged in status
	if request.method == 'POST' and form.validate_on_submit():
		flash("Your password has been reset!", 'success')

		# Reset the users password and log them in
		user.password = form.password.data
		login_user(user, True)

		return redirect(url_for('main.user_portal'))

	return render_template('/auth/password-reset.html',
				form=form, username=username, token=token)

@auth.route('/confirm')
@login_required
def confirm():
	token = request.args.get('token', None)

	if current_user.confirmed:
		login_user(current_user, True)
		return redirect( url_for('main.user_portal') )

	if current_user.confirm(token):
		flash("Thank you for confirming your account!", 'success')
	else:
		flash("The confirmation link is invalid or has expired.", 'error')

	return redirect(url_for('main.user_portal'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
	if current_user.is_authenticated:
		return redirect(url_for('main.index'))

	form = RegistrationForm()

	if request.method == 'POST':
		if form.validate_on_submit():
			user = User(
				email=form.email.data,
				username=form.username.data,
				password=form.password.data,
				confirmed=False
				)

			db.session.add(user)
			db.session.commit()

			# Join the public group
			g = Group.query.filter_by(name='Public').first()

			# Add the user to the public group
			user.joingroup(g)

			token = user.generate_confirmation_token()

			# Login the user
			login_user(user, True)

			# send a confirmation email
			if current_app.config['EMAILS']: #pragma: no cover
				sender = sendgrid.SendGridAPIClient(apikey=current_app.config['SENDGRID_API_KEY'])

				email = confirmation_email(
							to_email=current_user.email,
							from_email=current_app.config['FROM_EMAIL'],
							from_name=current_app.config['FROM_NAME'],
							link=url_for('auth.confirm', token=token, _external=True, _scheme='https'))

				response = sender.client.mail.send.post(request_body=email)

			return redirect(url_for('main.unconfirmed'))

	return render_template('auth/register.html', form=form)

@auth.route('/logout')
@login_required
def logout():
	logout_user()

	return redirect(url_for('main.index'))

"""
@auth.route('/2FA')
def two_factor_setup():
	if 'username' not in session:
		return redirect( url_for('main.index') )

	user = User.query.filter_by(username = session['username']).first()
	if user is None:
		return redirect( url_for('main.index') )

	# No cacheing!
	return render_template('auth/two-factor-setup.html'), 200, {
		'Cache-Control': 'no-cache, no-store, must-revalidate',
		'Pragma': 'no-cache',
		'Expires': '0'}

@auth.route('/qrcode')
def qrcode():
	if 'username' not in session:
		abort(404)

	user = User.query.filter_by(username = session['username']).first_or_404()

	# remove the session for security reasons
	del session['username']

	# Render the qrcode
	url = pyqrcode.create(user.get_totp_uri())
	stream = BytesIO()
	url.svg(stream, scale = 5)

	return stream.getvalue().encode('utf-8'), 200, {
		'Content-Type': 'image/svg+xml',
		'Cache-Control': 'no-cache, no-store, must-revalidate',
		'Pragma': 'no-cache',
		'Expires': '0'}
"""
