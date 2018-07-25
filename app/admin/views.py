from flask import render_template, session, redirect, url_for, flash, current_app, jsonify, request
from flask_login import login_required
from . import admin
from .. import db
from ..models import *
from ..decorators import admin_required, permission_required, confirmation_required
from ..decorators import superuser_required
import json
from flask_sqlalchemy import get_debug_queries
from sqlalchemy import and_, desc
from sqlalchemy.exc import IntegrityError
import re
import datetime
import sys
import pandas as pd
from flask_login import login_required, current_user
from .forms import UserForm, DeviceForm, FileUploadForm, ModelUploadForm, LogForm
from ..helpers import allowed_file
from werkzeug import secure_filename
import boto3
from sklearn.externals import joblib

s3 = boto3.resource('s3')

def allowed_file(fname):
	"""Return True if the extension is allowed"""
	ext = os.path.splitext(fname.lower())[1][1:]

	return True if ext in current_app.config['ALLOWED_EXTENSIONS'] else False

@admin.before_request
def before_request():
	if current_user:
		current_user.ping()

@admin.route('/')
@login_required
@admin_required
@confirmation_required
def index():
	title 		= 'Admin'
	users 		= User.query.all()
	instrument  = Instrument.query.all()
	groups 		= Group.query.all()
	models 		= Model.query.all()
	logs 		= Log.query.order_by(Log.opened.desc()).limit(100).all()

	return render_template('admin/index.html',
				title=title, users=users, instrument=instrument, groups=groups,
				models=models, logs=logs)

@admin.route('/edit-instrument', methods=['GET', 'POST'])
@login_required
@admin_required
@confirmation_required
def instrument():
	sn 				= request.args.get('sn', None)
	public_group 	= Group.query.filter_by(name='Public').first()

	if sn is None:
		i = Instrument()
	else:
		i = Instrument.query.filter_by(sn=sn).first_or_404()

	form = DeviceForm(obj=i)

	if sn is not None:
		# Update the device
		if request.method == 'POST' and form.validate_on_submit():
			form.populate_obj(i)

			if i.private == False:
				i.group = public_group

			try:
				db.session.add(i)
				db.session.commit()

				# Add event log
				i.log_event(message='Device updated by {} via admin form'.format(current_user.username))

				flash("{} Updated!".format(i.sn))
			except Exception as e:
				flash("There was an error: ".format(e), 'error')

			return redirect( url_for('admin.index') )
	else:
		# New Device
		if request.method == 'POST' and form.validate_on_submit():
			if form.discriminator.data == 'mit':
				i = MIT()
			elif form.discriminator.data == 'ebam':
				i = EBAM()
			elif form.discriminator.data == 'trex':
				i = TREX()
			elif form.discriminator.data == 'trex_pm':
				i = TrexPM()
			else:
				i = Instrument()

			form.populate_obj(i)
			if i.private == False:
				i.group = public_group

			# Set the user_id
			i.user_id = current_user.id

			try:
				db.session.add(i)
				db.session.commit()
			except IntegrityError as e:
				db.session.rollback()
				form.sn.errors.append("This SN is already in use; please try another!")

				return render_template('admin/add-instrument.html', title='Instrument',
									form=form, sn=sn)
			except Exception as e:
				print (e)

				return render_template('admin/add-instrument.html', title='Instrument',
									form=form, sn=sn)

			# Set the credentials
			i.set_credentials()

			flash("{} has been added!".format(i.sn), 'success')

			return redirect( url_for('admin.index') )

	return render_template('admin/add-instrument.html', title='Edit Instrument',
				form=form, sn=sn)

@admin.route('/user', methods=['GET', 'POST'])
@login_required
@admin_required
@confirmation_required
def user():
	id 		= request.args.get('id')
	user 	= User.query.get_or_404(id)
	form 	= UserForm(obj=user)

	if form.validate_on_submit():
		form.populate_obj(user)

		try:
			db.session.add(user)
			db.session.commit()

			flash("{} Updated!".format(user.username), 'sucess')
		except Exception:
			flash("Error: Could not update User", "error")

		return redirect( url_for('admin.index') )

	return render_template('admin/edit-user.html', title='User', form=form)

@admin.route('/model-upload', methods=['GET', 'POST'])
@admin_required
@confirmation_required
def upload_model():
	form = ModelUploadForm()

	if request.method == 'POST' and form.validate_on_submit():
		file = request.files['file']

		if file and allowed_file(file.filename):
			new = Model()

			new.filename = secure_filename(file.filename)
			new.label = request.form.get('label')
			new.description = request.form.get('description', None)
			new.rmse = request.form.get('rmse', None)
			new.mae = request.form.get('mae', None)
			new.r2 = request.form.get('r2', None)

			# Save the file
			try:
				file.save(os.path.join(current_app.config['MODELS_DIR'], file.filename))

				db.session.add(new)
				db.session.commit()

				flash("{} has been uploaded.".format(file.filename), 'info')
			except Exception as e:
				print (e)
				flash("Could not save the model: {}".format(e), 'error')

		return redirect( url_for('admin.index') )

	return render_template('admin/add-model.html', title='Add Model', form=form)

@admin.route('/log', methods=['GET', 'POST'])
@admin_required
@confirmation_required
def log():
	"""
	"""
	id = request.args.get('id', None)
	form = LogForm()

	# new log (empty form)
	if request.method == 'POST' and form.validate_on_submit():
		data = dict()

		data['level'] = request.form.get('level')
		data['instr_sn'] = request.form.get('instrument')
		data['message'] = request.form.get('message', None)

		db.session.add(Log.create(data))
		db.session.commit()

		flash("Added log", "info")

		return redirect( url_for('admin.index') )

	return render_template('admin/add-log.html', title='Add Log', form=form)

"""
@admin.route('/file-upload', methods=['GET', 'POST'])
@admin_required
@confirmation_required
def upload_file():
	#Upload a file to a specific instrument
	form 	= FileUploadForm()
	bucket 	= s3.Bucket(current_app.config['AWS_BUCKET'])

	if request.method == 'POST':
		if form.validate_on_submit():
			file 	= request.files['file']
			dev_id 	= request.form['device']
			device 	= Instrument.query.get(dev_id)
			fname 	= secure_filename(file.filename)

			keyname = "{}/{}".format(device.sn, fname)

			aws_entry = AWS.query.filter_by(key = keyname).first()

			# If it already exists, update the size_mb
			if aws_entry is not None:
				flash("This file already exists. You are updating it.")
			else:
				aws_entry = AWS(
								key = keyname,
								bucket_name = bucket.name,
								date = datetime.date.today(),
								device_id = dev_id,
								private = True
								)

				db.session.add(aws_entry)
				db.session.commit()

			bucket.put_object(Key = keyname, Body = file)

			flash("{} has been added to AWS".format(keyname))

			return redirect( url_for('admin.index') )

	return render_template('admin/add-file.html', title = 'Upload File', form = form)
"""

@admin.route('/drop-user')
@superuser_required
@confirmation_required
def drop_user():
	id 		= request.args.get('id')
	user 	= User.query.get_or_404(id)

	user.drop()

	flash("User has been dropped. FOREVER.", 'success')

	return redirect( url_for('admin.index') )

@admin.route('/drop-instrument')
@superuser_required
@confirmation_required
def drop_instrument():
	"""DELETE an instrument from the database
	"""
	id 		= request.args.get('id')
	instr 	= Instrument.query.get_or_404(id)

	instr.drop()

	flash("Instrument has been deleted along with its children :/", 'success')

	return redirect( url_for('admin.index') )
