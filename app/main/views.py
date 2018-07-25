from flask import render_template, session, redirect, url_for, flash, current_app, jsonify, request
from flask import abort
from . import main
from .. import db, cache, sentry
from ..models import User, Credentials, Instrument, Log
from .forms import TokenForm, UserSettingsForm
from ..decorators import admin_required, permission_required, confirmation_required
import json
from flask_sqlalchemy import get_debug_queries
from sqlalchemy import and_
import re
import datetime
from datetime import timedelta
import boto3
from geojson import FeatureCollection
from sqlalchemy.sql.expression import func
from functools import lru_cache

import time

s3_client = boto3.client('s3')

from flask_login import login_required, current_user

@main.before_request
def before_request():
	if current_user:
		current_user.ping()

@main.route('/')
def index():
	title = 'Tata Center A.Q.'

	return render_template('main/home.html', title=title)


# # should these just be the public ones? and just recently updated
@cache.memoize(60*60) # store
def get_instruments(cache_ts):
	sess = db.session.query(Instrument)

	instruments = sess.filter(
		Instrument.longitude.isnot(None)).filter(Instrument.latitude.isnot(None)).filter(Instrument.last_updated >= cache_ts).filter(func.length(Instrument.latitude) > 0).all()

	features = []

	for each in current_app.config['ALLOWED_POLLUTANTS']:
		# grab all instruments that meet specs
		ins = [i for i in instruments if i.has(each)]
		feature = {
			'value': each,
			'label': each.upper(),
			'geo_points': FeatureCollection([i.to_geojson_feature(each) for i in ins]),
		}
		features.append(feature)
	return features

@main.route('/map')
def map():
	h = time.time()
	title = "Map"
	# minimum timestamp to grab data from
	min_ts = datetime.datetime.utcnow() - timedelta(hours=current_app.config['MAX_AGE_ON_MAP_HRS'])
	cache_ts = min_ts.replace(minute=0, second=0, microsecond=0) # ensure queries made in one hour are similar
	features = get_instruments(cache_ts)
	return render_template("main/map.html", title=title, features=features)

@main.route('/unconfirmed')
def unconfirmed():
	if current_user.confirmed:
		return redirect( url_for('main.index') )

	return render_template('auth/unconfirmed.html')

@main.route('/user-settings', methods=['GET', 'POST'])
@login_required
@confirmation_required
def change_settings():
	form = UserSettingsForm()

	user = User.query.get_or_404(current_user.id) # probably don't need this..
	if request.method == 'POST' and form.validate_on_submit():
		# If the old password is incorrect, save nothing..
		if not current_user.verify_password(form.old_password.data):
			flash("I'm sorry. You're old password is incorrect.", 'danger')

			return redirect( url_for('main.change_settings') )

		# Check to make sure the username is valid (either the same as current_user, or not in the db)
		username = form.username.data

		if username != current_user.username:
			if User.query.filter_by(username = username).count() == 0:
				current_user.username = form.username.data
			else:
				flash("I'm sorry, but this username is already taken", 'danger')

				return redirect( url_for('main.change_settings') )

		# If the new password field is filled out, update!
		if form.password.data:
			current_user.password = form.password.data

		db.session.add(current_user)
		db.session.commit()

		flash("Thanks for updating your settings", 'success')

	form.username.data = current_user.username

	return render_template('main/user-settings.html', form=form)

@main.route('/devices')
@login_required
@confirmation_required
def user_portal():
	"""From the devices page, the user should be able to get view the devices they
	own and register new devices.
	"""
	user = User.query.get_or_404(current_user.id)

	return render_template('main/devices.html', user=user, devices=user.following)

@main.route('/device')
def view_public_device():
	"""This is the public view for any instrument
	"""
	sn = request.args.get('sn')
	device = Instrument.query.filter_by(sn=sn).first_or_404()
	private = False

	# Get the last 100 logs
	logs = device.logs.order_by(Log.opened.desc()).limit(100).all()

	# Move this to JS in the future...
	today = datetime.datetime.today()

	datepicker_start = (today + timedelta(days=-3)).strftime('%m/%d/%Y')
	datepicker_end = today.strftime('%m/%d/%Y')

	# Only show if the user is either a manager or it is public or it belongs to them!
	# Maybe instead of redirecting, we could just show an error message?
	if not current_user.canview(device):
		abort(403)

	if current_user.can_view_research_data:
		private = True

	return render_template('main/device.html', user=current_user, device=device,
			private=private, datepicker_start=datepicker_start,
			datepicker_end=datepicker_end, logs=logs)

"""
@main.route('/downloads')
@login_required
@confirmation_required
def download_data():
	#Public view for data downloads
	#Figure out a way to return data for developers or not...

	coreid 	= request.args.get('sn', None)
	hidden 	= request.args.get('hidden', True)
	files 	= []

	# If there is no ind device, grab them all and show a dropdown box
	if coreid is None:
		devices = current_user.following()
	else:
		dev = Instrument.query.filter_by(sn = coreid).first_or_404()
		if current_user.canview(dev):
			devices = [dev]
		else:
			flash("You do not have permission to view this device!")
			return redirect(url_for('main.index'))

	for each in devices:
		f = each.datafiles
		if not current_user.is_researcher():
			f = f.filter_by(private = False)

		files = files + f.all()

	return render_template('main/downloads.html',
				user = current_user,
				data = files,
				s3_client = s3_client)
"""
@main.route('/api-tokens', methods=['GET', 'POST'])
@login_required
@confirmation_required
def user_api():
	tokens 	= current_user.credentials.all()
	form 	= TokenForm()

	if request.method == 'POST' and form.validate_on_submit():
		token = Credentials(name=form.name.data, user_id=current_user.id)

		db.session.add(token)
		db.session.commit()

		return redirect( url_for('main.user_api') )

	return render_template('main/user-api-tokens.html',
							tokens=tokens, form=form)

@main.route('/remove-api-token')
@login_required
@confirmation_required
def drop_token():
	id 		= request.args.get('id')
	token 	= current_user.credentials.filter_by(id=id).first()

	if token is None:
		flash("You do not have permission to alter this token.", 'error')

	token.drop()

	return redirect( url_for('main.user_api') )

@main.route('/api-docs')
def api_docs():
	return render_template('main/api-docs.html')
