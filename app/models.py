"""Models.py."""
from . import db, login_manager, sentry
import os
from io import StringIO
import random
from .utilities import safe_cast
from datetime import datetime, timedelta
import pytz
from flask import current_app, url_for, abort, send_from_directory
import string
from app.exceptions import EmptyDataFrameException, S3Exception
import dateutil.parser
import pandas as pd
from .helpers import calculate_start_timestamp, to_timezone
from sqlalchemy import desc
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm import backref
import base64
import onetimepass
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from flask_login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import botocore
from sklearn.externals import joblib
import numpy as np
from geojson import Point, Feature, FeatureCollection

@login_manager.user_loader
def load_user(user_id):
	"""Load the current user."""
	return User.query.get(int(user_id))


groups = db.Table('groups',
			db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
			db.Column('group_id', db.Integer, db.ForeignKey('group.id')),
			)


class Permission:
	"""Permission Model."""

	FOLLOW = 0x01
	API_READ = 0x02
	API_WRITE = 0x04
	VIEW_RESEARCH_DATA = 0x08
	ADMINISTER = 0x80
	DELETE = 0x90


class Role(db.Model):
	__tablename__  = 'roles'

	id 			= db.Column(db.Integer, primary_key=True)
	name 		= db.Column(db.String(64), unique=True)
	default 	= db.Column(db.Boolean, default=False, index=True)
	permissions = db.Column(db.Integer)
	users 		= db.relationship('User', backref='role') # lazy='dynamic'

	@staticmethod
	def insert_roles():
		roles = {
			'User': (Permission.FOLLOW | Permission.API_READ, True),
			'Node': (Permission.FOLLOW | Permission.API_WRITE | Permission.API_READ, False),
			'Researcher': (Permission.FOLLOW | Permission.API_READ | Permission.API_WRITE | Permission.VIEW_RESEARCH_DATA, False),
			'Manager': (Permission.FOLLOW | Permission.API_READ | Permission.ADMINISTER | Permission.VIEW_RESEARCH_DATA | Permission.API_WRITE, False),
			'Administrator': (0xff, False)
			}

		for r in roles:
			role = Role.query.filter_by(name=r).first()

			if role is None:
				role = Role(name=r, permissions=roles[r][0], default=roles[r][1])

				db.session.add(role)
				db.session.commit()
			else:
				role.permissions = roles[r][0]

				db.session.add(role)
				db.session.commit()

	def __repr__(self):
		return "{}".format(self.name)


class User(UserMixin, db.Model):
	__tablename__ = 'users'

	SENTRY_USER_ATTRS = ['username', 'role_id', 'email']

	id 				= db.Column(db.Integer, primary_key=True)
	email 			= db.Column(db.String(64), nullable=False, unique=True, index=True)
	username 		= db.Column(db.String(64), nullable=False, unique=True, index=True)
	confirmed 		= db.Column(db.Boolean, default=False)
	_password_hash 	= db.Column(db.String(128))
	otp_secret 		= db.Column(db.String(16))
	member_since 	= db.Column(db.DateTime(), default=datetime.utcnow)
	last_seen 		= db.Column(db.DateTime(), default=datetime.utcnow,
								onupdate=datetime.utcnow)
	role_id 		= db.Column(db.Integer, db.ForeignKey('roles.id'))
	credentials		= db.relationship('Credentials', backref='User', lazy='dynamic')
	devices 		= db.relationship('Instrument', backref='owner', lazy='dynamic')

	def __init__(self, **kwargs):
		super(User, self).__init__(**kwargs)

		if self.otp_secret is None:
			self.otp_secret = base64.b32encode(os.urandom(10)).decode('utf-8')

		if self.role is None:
			if self.email in current_app.config['ADMINS']:
				self.role = Role.query.filter_by(permissions = 0xff).first()
			else:
				self.role = Role.query.filter_by(default=True).first()

	@property
	def password(self):
		raise AttributeError('password is not a reliable readable attribute.')

	@password.setter
	def password(self, password):
		self._password_hash = generate_password_hash(password)

	def ping(self):
		self.last_seen = datetime.utcnow()

		db.session.commit()

		return True

	def generate_confirmation_token(self, expiration=3600 * 24):
		s = Serializer(current_app.config['SECRET_KEY'], expiration)

		return s.dumps({'confirm': self.id})

	def confirm(self, token):
		s = Serializer(current_app.config['SECRET_KEY'])
		try:
			data = s.loads(token)
		except:
			return False

		if data.get('confirm') != self.id:
			return False

		self.confirmed = True

		db.session.add(self)
		db.session.commit()

		return True

	def verify_password(self, password):
		return check_password_hash(self._password_hash, password)

	def can(self, permissions):
		return self.role is not None and \
			(self.role.permissions & permissions) == permissions

	@property
	def can_manage(self):
		return self.can(Permission.ADMINISTER)

	@property
	def can_delete(self):
		return self.can(Permission.DELETE)

	@property
	def can_write(self):
		return self.can(Permission.API_WRITE)

	@property
	def can_view_research_data(self):
		return self.can(Permission.VIEW_RESEARCH_DATA)

	def ismember(self, group):
		return self.groups.filter_by(id=group.id).first() is not None

	def joingroup(self, group):
		if not self.ismember(group):
			self.groups.append(group)

		return self

	def leavegroup(self, group):
		# cannot leave the public group
		if self.ismember(group) and group.name is not 'Public':
			self.groups.remove(group)

		return self

	def isowner(self, device):
		"""Return true if superuser or owner of device"""
		if device.owner is self or self.can_manage:
			return True

		return False

	def canview(self, device):
		if self.can(Permission.ADMINISTER):
			return True

		return device in self.following

	@property
	def following(self):
		"""Returns a list of Instrument instances that contains all devices
		in groups the user belongs to as well as any devices they own (but are
		not yet placed within a group). If the person is an admin, return all
		Instruments.
		"""
		query = None
		if self.can_manage:
			query = Instrument.query
		else:
			# Get the group ids that the user belongs to
			group_ids = [g.id for g in self.groups]

			query = Instrument.query.filter((Instrument.group_id.in_(group_ids) |
							(Instrument.owner == self)))

		return query

	def set_credentials(self):
		if self.credentials.count() == 0:
			c = Credentials(user_id=self.id)

			db.session.add(c)
			db.session.commit()

			return True

		return False

	@property
	def api_token(self):
		"""Return the current API token"""
		_token = self.credentials.first()
		if _token is not None:
			_token = _token.key

		return _token

	def drop(self):
		for each in self.devices:
			each.user_id = None

			db.session.add(each)

			db.session.commit()

			db.session.delete(self)
			db.session.commit()

		return True

	def __str__(self):
		return self.username

	def __repr__(self):
		return "{}".format(self.username)


class AnonymousUser(AnonymousUserMixin):
	def can(self, permissions):
		return False

	def is_administrator(self):
		return False

	def ping(self):
		pass

	def canview(self, dev):
		if dev.private == False:
			return True

		return False

	@property
	def can_view_research_data(self):
		return False

	def isowner(self, dev):
		return False


class Group(db.Model):
	__tablename__ = 'group'

	id 		= db.Column(db.Integer, primary_key=True)
	name 	= db.Column(db.String(64), unique=True)
	members = db.relationship('User', secondary=groups, lazy='dynamic',
				backref=db.backref('groups', lazy='dynamic', order_by=name))
	devices = db.relationship('Instrument', backref='group', lazy='dynamic')

	def __init__(self, name, **kwargs):
		self.name = name

	@staticmethod
	def insert_groups():
		groups = ['Public', 'Tata', 'Trex2017', 'USHA', 'UT-Austin']

		for g in groups:
			group = Group.query.filter_by(name=g).first()

			if group is None:
				group = Group(name=g)

				db.session.add(group)
				db.session.commit()

	def __repr__(self):
		return self.name


class Credentials(db.Model):
	__tablename__	= 'credentials'

	def key(length=24):
		return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(length))

	id 			= db.Column(db.Integer, primary_key=True)
	created 	= db.Column(db.DateTime, default=datetime.utcnow)
	key 		= db.Column(db.String(24), unique=True, default=key)
	name 		= db.Column(db.String(64))
	user_id		= db.Column(db.Integer, db.ForeignKey('users.id'))
	instr_sn	= db.Column(db.String(24), db.ForeignKey('instrument.sn'))

	@property
	def can_write(self):
		if (self.User and self.User.can(Permission.API_WRITE)) or self.parent:
			return True
		else:
			return False

	@property
	def can_drop(self):
		if self.User and self.User.can(Permission.DELETE):
			return True

		return False

	def get_scope(self):
		"""Return a list of scopes"""
		_scopes = ['READ']

		if self.can_write:
			_scopes.append('WRITE')

		return _scopes

	def drop(self):
		db.session.delete(self)
		db.session.commit()

		return True

	def __repr__(self):
		return "{}".format(self.key)


login_manager.anonymous_user = AnonymousUser

################################################################################
##########################  DB Models for API  #################################
################################################################################


class AWS(db.Model):
	__tablename__ = 'aws'

	id 				= db.Column(db.Integer, primary_key=True)
	bucket_name 	= db.Column(db.String(24), nullable=False, index=True)
	key 			= db.Column(db.String(48), nullable=False)
	date 			= db.Column(db.Date, index=True)
	length 			= db.Column(db.String(12), index=True, default='1d')
	private 		= db.Column(db.Boolean, index=True)
	last_modified 	= db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
	size_mb 		= db.Column(db.Float, default=0.0)
	downloads 		= db.Column(db.Integer, default=0)
	device_id 		= db.Column(db.Integer, db.ForeignKey('instrument.id'))

	__table_args__ = (UniqueConstraint('bucket_name', 'key', name='uix_1'),)

	# Eventually, remove file from S3 as well
	def drop(self):
		db.session.delete(self)

		db.session.commit()

		return True

	def presigned_url(self, s3_client):
		url = s3_client.generate_presigned_url(
							ClientMethod='get_object',
							Params={'Bucket': self.bucket_name, 'Key': self.key})
		return url

	def increment(self):
		"""Increment the number of times this file has been downloaded"""
		self.downloads += 1




class Instrument(db.Model):
	__tablename__ = 'instrument'

	id 				= db.Column(db.Integer, primary_key=True)
	sn 				= db.Column(db.String(24), unique=True, index=True, nullable=False)
	particle_id 	= db.Column(db.String(24))
	ip 				= db.Column(db.String(24))
	discriminator 	= db.Column(db.String(24), index=True, default='other')
	latitude 		= db.Column(db.String(12))
	longitude 		= db.Column(db.String(12))
	location 		= db.Column(db.String(24))
	city 			= db.Column(db.String(48), index=True)
	country			= db.Column(db.String(8), index=True)
	timezone 		= db.Column(db.String(24))
	outdoors 		= db.Column(db.Boolean, default=True)
	model 			= db.Column(db.String(48), index=True)
	description 	= db.Column(db.Text)
	private 		= db.Column(db.Boolean, default=True)
	active 			= db.Column(db.Boolean, default=False)
	creation_date 	= db.Column(db.DateTime, default=datetime.utcnow)
	last_updated 	= db.Column(db.DateTime, default=datetime.utcnow,
						onupdate=datetime.utcnow)
	credentials 	= db.relationship('Credentials', uselist=False,
						backref='parent', cascade='all, delete-orphan')
	user_id			= db.Column(db.Integer, db.ForeignKey('users.id'))
	group_id 		= db.Column(db.Integer, db.ForeignKey('group.id'))
	datafiles 		= db.relationship('AWS', backref='device', lazy='dynamic')
	logs 			= db.relationship('Log', backref='device', lazy='dynamic',
						cascade='all, delete-orphan')

	public_cols 	= ['value']
	private_cols 	= public_cols + []

	params 			= []

	__mapper_args__ = {'polymorphic_on': discriminator, 'polymorphic_identity': 'other'}

	@staticmethod
	def create(data):
		instrument = Instrument()

		instrument.from_dict(data)

		return instrument

	def get_url(self):
		return url_for('api_1_0.get_device', sn=self.sn, _external=True, _scheme='https')

	def has(self, pollutant):
		"""Return True if the pollutant exists for this instrument
		"""
		return pollutant in self.params

	def set_credentials(self):
		if self.credentials:
			self.credentials.drop()

		c = Credentials(instr_sn=self.sn)

		db.session.add(c)
		db.session.commit()

		return True

	def ismember(self, group):
		return self.group is group

	def joingroup(self, group):
		if not self.ismember(group):
			self.group = group

		db.session.add(self)
		db.session.commit()

		return True

	def leavegroup(self, group):
		if self.ismember(group):
			self.group_id = None

		db.session.add(self)
		db.session.commit()

		return True

	def _to_geojson_feature(self, pollutant=None):
		"""Load an instrument and return in geosjon format to display on
		the MapBox map.
		"""
		location = self.location
		if location != '':
			location = "{}, {}".format(location, self.city)
		else:
			location = self.city

		feature = Feature(
					geometry=Point((float(self.longitude), float(self.latitude))),
					properties={
						'title':self.sn,
						'value': None,
						'description': self.description,
						'unit': None,
						'location': location,
						'flag': None,
						'timestamp': None,
						'public': not self.private,
						'data_id': None,
						'url': url_for('main.view_public_device', sn=self.sn)
						}
					)

		return feature

	def to_json(self):
		return {
			'sn': 			self.sn,
			'location': 	self.location,
			'city': 		self.city,
			'country': 		self.country,
			'timezone':		self.timezone,
			'outdoors':		self.outdoors,
			'model':		self.model,
			'outdoors':		self.outdoors,
			'last_updated': self.last_updated.isoformat(),
			'url':			self.get_url(),
			'latitude':		self.latitude,
			'longitude':	self.longitude
			}

	def from_dict(self, data, partial_update=False):
		# Fix issue with type/discriminator
		for field in ['sn']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				if not partial_update:
					raise KeyError

		# all other optional fields
		for field in ['particle_id', 'latitude', 'longitude', 'location',
						'city', 'description', 'country', 'outdoors', 'ip',
						'timezone', 'private', 'type', 'model', 'active']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				pass

	def _get_data_model(self):
		return self.__class__.results.property.mapper.class_

	def most_recent_datapoint(self):
		"""Return the most recent data point
		"""
		m = self._get_data_model()

		q = m.query.filter(m.instr_sn==self.sn).order_by(m.timestamp.desc()).first()

		return q

	def df_from_query(self, query, cols_to_keep=[], developer=False, dropna=False):
		"""Create a dataframe from a query.
		"""
		#cols_to_keep is a list of the columns to export. If none, all are kept.
		#developer dictates whether to export private cols
		df = pd.read_sql(
				query.statement,
				query.session.bind,
				index_col='timestamp',
				parse_dates=True
				)

		del df['id']

		# Delete all columns not in cols_to_keep
		#if not developer and cols_to_keep is not None:
		if cols_to_keep is not None:
			for col in df.columns:
				if not col in cols_to_keep:
					del df[col]

		# If the instrument has a timezone, add a column with local_time
		if self.timezone:
			df['timestamp_local'] = df.index.map(lambda x: to_timezone(x, self.timezone, replace=True, isoformat=False))

			# Reorder to make a bit nicer
			df = df.reindex(['timestamp_local'] + list([a for a in df.columns if a != 'timestamp_local']), axis=1)
		else:
			df['timestamp_local'] = None

		return df.sort_index()

	def csv_to_aws(self, bucket_name, t0, tf, developer=False, s3=None, dropna=False):
		"""Generate a CSV containing the data for a single day or a single month.
		t0 and tf should be datetime.date objects.

		If developer is True, add all data, not just finalized data.

		Generate a csv for data between t0 and tf and dump to csv.
		Returns keyname if uploaded successfuly.
		"""
		keyname = "{}/DATA_{}".format(self.sn, t0.strftime("%Y%m%d"))

		dt = (tf - t0).days

		# If more than 1 day, add the end date as well
		if dt > 1:
			keyname += "_{}".format(tf.strftime("%Y%m%d"))

		if developer:
			keyname += "_DEVELOPER"

		keyname += ".csv"

		# Get the data model
		data_model = self._get_data_model()

		# Query the data between the two timestamps
		q = data_model.query.filter(data_model.timestamp >= t0, data_model.timestamp <= tf)

		# Get the dataframe
		df = self.df_from_query(q, cols_to_keep=self.cols_to_keep,
						developer=developer, dropna=dropna)

		if df.empty:
			raise EmptyDataFrameException("DataFrame Empty")

		# Create a CSV buffer to upload directly to S3
		csv_buffer = df.to_csv(None, date_format='%Y-%m-%dT%H:%M:%SZ')

		fsize = len(csv_buffer) * 1e-6

		# Check to see if the key already exists
		key = AWS.query.filter_by(key=keyname, bucket_name=bucket_name).first()

		# Create a new key
		if key is None:
			key = AWS(bucket_name=bucket_name, key=keyname, date=t0, length=dt,
						size_mb=fsize, device_id=self.id, private=developer)

			db.session.add(key)
			db.session.commit()
		# If it already exists, update it
		else:
			key.date = t0
			key.length = dt
			key.size_mb = fsize

			db.session.add(key)
			db.session.commit()

		try:
			s3.Object(bucket_name=bucket_name, key=keyname).put(Body=csv_buffer)
		except botocore.exceptions.ClientError as e:
			raise S3Exception(e.response['Error'])

		return key

	def log_event(self, message, level='INFO'):
		"""After an event is logged, check to inform the owner of the device
		and email them if necessary or notify them via pushbutton. Maybe build
		out a pushbutton/notifier decorator

		Event should be a dictionary
		"""
		data = dict(instr_sn=self.sn, message=message, level=level)

		# Log the event
		log = Log.create(data)

		db.session.add(log)
		db.session.commit()

		# Send push notifications for critical and information things
		if level in ['CRITICAL']:
			pass

		return True

	def evaluate(self, data):
		"""Accept a dictionary of data and evaluate all models where applicable.
		Returns an instance of the new datapoint after evaluation.
		"""
		return data

	@property
	def api_token(self):
		"""Return the current API token"""
		return self.credentials

	def fakedata(self, n=100, interval='min', direction='forward'):
		"""Generate n fake data points"""
		data_model = self._get_data_model()

		t0 = datetime.utcnow()

		for i in range(n):
			dt = timedelta(hours=i) if interval == 'hours' else timedelta(minutes=i)
			t = t0 + dt if direction == 'formward' else t0 - dt

			new = data_model.fake(t, self.sn)

			db.session.add(new)
			db.session.commit()

		return

	def update(self):
		self.last_updated = datetime.utcnow()

		db.session.add(self)

		return True

	def drop(self):
		db.session.delete(self)
		db.session.commit()

		return True

	def __repr__(self):
		return "<{}>".format(self.sn)


class Orphan(Instrument):
	__tablename__	= 'orphan'
	__mapper_args__	= {'polymorphic_identity': 'orphan'}

	id 			= db.Column(db.Integer, db.ForeignKey('instrument.id'), primary_key=True)
	results 	= db.relationship('Data', backref='device', cascade='all, delete-orphan', lazy='dynamic')

	ml_model_id 	= db.Column(db.Integer, db.ForeignKey('model.id'))
	ml_model 		= db.relationship('Model', foreign_keys=[ml_model_id], uselist=False)

	cols_to_keep = ['value', 'parameter', 'unit', 'flag', 'instr_sn']

	def __init__(self, private=True, **kwargs):
		super(Orphan, self).__init__(discriminator='orphan', **kwargs)

	@property
	def public_cols(self):
		return ['value', 'parameter', 'unit', 'flag', 'status', 'instr_sn']

	@property
	def private_cols(self):
		return self.public_cols

	@property
	def params(self):
		return list(self.get_param())

	@staticmethod
	def create(data):
		instrument = Orphan()

		instrument.from_dict(data)

		return instrument

	def get_param(self):
		"""Try to guess the param based on model
		Eventually move this to helpers!
		"""
		lookup = {'2BTech 202': 'o3', }

		if self.model in lookup.keys():
			return lookup[self.model]

		return 'na'

	def _plotly(self, span='1d', researcher=False, **kwargs):
		"""Return data in a plotly-readable format"""
		t0 = calculate_start_timestamp(span)

		# Retrieve the data
		data = db.session.query(Data).filter(Data.instr_sn==self.sn,
					Data.timestamp >= t0).order_by(desc(Data.timestamp))

		# initialize results
		results = dict(meta=dict(title='', xlabel='', units=''), data=[])

		# Set the keys
		results['meta']['keys'] = ['value']

		# data should be returned as an array of dictionaries
		if data.count() != 0:
			# Set the units
			results['meta']['units'] 	= [data.first().unit]
			results['meta']['param']	= self.get_param().upper()
			results['meta']['title'] 	= "{} | {}, {}".format(self.sn, self.location, self.city)
			results['meta']['xlabel']	= "Datetime [ {} ]".format(self.timezone) if self.timezone else "Datetime [ UTC ]"

			# Export the data
			results['data'] = [each._plotly(researcher=researcher) for each in data]

		return results

	def to_geojson_feature(self, pollutant=None):
		"""Load an instrument and return in geosjon format to display on
		the MapBox map.
		"""
		feature = self._to_geojson_feature(pollutant=pollutant)

		# get the most recent datapoint
		recent = self.most_recent_datapoint()

		# adjust the params to fit Orphan
		feature['properties']['unit'] = self.get_param()
		feature['properties']['value'] = recent.value
		feature['properties']['flag'] = recent.flag
		feature['properties']['timestamp'] = recent.timestamp.isoformat()

		return feature


class MIT(Instrument):
	__tablename__ 	= 'mit_instrument'
	__mapper_args__	= {'polymorphic_identity': 'mit'}

	id 			= db.Column(db.Integer, db.ForeignKey('instrument.id'), primary_key=True)
	results 	= db.relationship('MITData', backref='device', cascade='all, delete-orphan', lazy='dynamic')

	so2_model_id 	= db.Column(db.Integer, db.ForeignKey('model.id'))
	co_model_id 	= db.Column(db.Integer, db.ForeignKey('model.id'))
	ox_model_id 	= db.Column(db.Integer, db.ForeignKey('model.id'))
	nox_model_id	= db.Column(db.Integer, db.ForeignKey('model.id'))
	pm_model_id		= db.Column(db.Integer, db.ForeignKey('model.id'))

	so2_model = db.relationship('Model', foreign_keys=[so2_model_id], uselist=False)
	co_model = db.relationship('Model', foreign_keys=[co_model_id], uselist=False)
	ox_model = db.relationship('Model', foreign_keys=[ox_model_id], uselist=False)
	nox_model = db.relationship('Model', foreign_keys=[nox_model_id], uselist=False)
	pm_model = db.relationship('Model', foreign_keys=[pm_model_id], uselist=False)


	cols_to_keep = ['instr_sn', 'co', 'o3', 'so2', 'nox', 'pm1', 'pm25', 'pm10', 'rh_i', 'temp_i', 'flag']

	public_keys 	= ['CO', 'O3', 'NOx', 'SO2', 'PM1', 'PM25', 'PM10', 'RH', 'Temperature']
	private_keys 	= public_keys + ['CO_WE', 'NOX_WE', 'SO2_WE', 'O3_WE']

	public_units 	= ['ppb', 'ppb', 'ppb', 'ppb', 'ug/m3', 'ug/m3', 'ug/m3', '%', 'degC']
	private_units 	= public_units + ['mV', 'mV', 'mV', 'mV']

	params = ['pm1', 'pm25', 'pm10', 'co', 'o3', 'nox', 'so2']

	def __init__(self, private=True, **kwargs):
		super(MIT, self).__init__(discriminator='mit', **kwargs)

	@property
	def public_cols(self):
		cols = ['instr_sn', 'co', 'o3', 'so2', 'nox', 'pm1', 'pm25',
							'pm10', 'rh_i', 'temp_i', 'flag', 'last_updated']
		return cols

	@property
	def private_cols(self):
		cols = [m.key for m in MITData.__table__.columns]

		cols.remove('id')
		cols.remove('timestamp')

		return cols

	def evaluate(self, data):
		"""Evaluate the model and return an instance of a new MITData
		"""
		# Iterate over each possible data point and try to load the model, evaluate, and save
		"""
		if self.so2_model:
			data['so2_model_id'] = self.so2_model_id

		if self.co_model:
			data['co_model_id'] = self.co_model_id

		if self.nox_model:
			data['nox_model_id'] = self.nox_model_id

		if self.ox_model:
			data['ox_model_id'] = self.ox_model_id

		if self.pm_model:
			data['pm_model_id'] = self.pm_model_id
		"""

		return data

	@staticmethod
	def create(data):
		instrument = MIT()

		instrument.from_dict(data)

		return instrument

	def _plotly(self, span='1d', researcher=False, **kwargs):
		"""Return data in a plotly-readable format"""
		t0 = calculate_start_timestamp(span)

		# Retrieve the data
		data = db.session.query(MITData).filter(MITData.instr_sn == self.sn,
					MITData.timestamp >= t0).order_by(desc(MITData.timestamp))

		# initialize results
		results = dict(meta=dict(title='', xlabel='', units=''), data=[])

		# Set the keys
		if researcher:
			results['meta']['keys'] = self.private_keys
			results['meta']['units'] = self.private_units
		else:
			results['meta']['keys'] = self.public_keys
			results['meta']['units'] = self.public_units

		# data should be returned as an array of dictionaries
		if data.count() != 0:
			results['meta']['title'] 	= "{} | {}, {}".format(self.sn, self.location, self.city)
			results['meta']['xlabel']	= "Datetime [ {} ]".format(self.timezone) if self.timezone else "Datetime [ UTC ]"

			# Export the data
			results['data'] = [each._plotly(researcher=researcher) for each in data]

		return results

	def to_geojson_feature(self, pollutant=None):
		"""Load an instrument and return in geosjon format to display on
		the MapBox map.
		"""
		feature = self._to_geojson_feature(pollutant=pollutant)

		# get the most recent datapoint
		recent = self.most_recent_datapoint()

		unit = None
		value = None

		if pollutant == 'so2':
			unit, value = 'ppb', recent.so2
		elif pollutant == 'co':
			unit, value = 'ppb', recent.co
		elif pollutant == 'nox':
			unit, value = 'ppb', recent.nox
		elif pollutant == 'o3':
			unit, value = 'ppb', recent.o3
		elif pollutant == 'pm1':
			unit, value = 'ug/m3', recent.pm1
		elif pollutant == 'pm25':
			unit, value = 'ug/m3', recent.pm25
		elif pollutant == 'pm10':
			unit, value = 'ug/m3', recent.pm10
		else:
			unit, value = None, None

		# adjust the params to fit Orphan
		feature['properties']['unit'] = unit
		feature['properties']['value'] = value
		feature['properties']['timestamp'] = recent.timestamp.isoformat()
		feature['properties']['flag'] = recent.flag

		return feature


class EBAM(Instrument):
	__tablename__ 	= 'ebam_instrument'
	__mapper_args__ = {'polymorphic_identity': 'ebam'}

	id = db.Column(db.Integer, db.ForeignKey('instrument.id'), primary_key=True)
	results = db.relationship('EBamData', backref='device', cascade='all, delete-orphan', lazy='dynamic')

	cols_to_keep = None
	ml_model = None

	public_keys 	= ['Conc. (1hr)', 'Conc. (10min)', 'Wind Speed', 'Wind Dir.', 'Ambient Temp.']
	private_keys	= ['Conc. (1hr)', 'Conc. (10min)', 'Wind Speed', 'Wind Dir.', 'Ambient Temp.']
	public_units   	= [ 'ug/m3', 'ug/m3', 'km/h', 'NE', 'degC']
	private_units 	= [ 'ug/m3', 'ug/m3', 'km/h', 'NE', 'degC']

	params = ['pm25']

	def __init__(self, **kwargs):
		super(EBAM, self).__init__(discriminator='ebam', **kwargs)

	@property
	def public_cols(self):
		cols = [m.key for m in EBamData.__table__.columns]

		cols.remove('id')

		return cols

	@property
	def private_cols(self):
		return self.public_cols

	def evaluate(self, data):
		"""Evaluate the dictionary per the most up-to-date model of the parent
		Returns a dictionary.
		"""
		return data

	@staticmethod
	def create(data):
		instrument = EBAM()

		instrument.from_dict(data)

		return instrument

	def _plotly(self, span='1d', researcher=False, **kwargs):
		"""Return data in a plotly-readable format"""
		t0 = calculate_start_timestamp(span)

		# Retrieve the data
		data = db.session.query(EBamData).filter(EBamData.instr_sn == self.sn,
		EBamData.timestamp >= t0).order_by(desc(EBamData.timestamp))

		# initialize results
		results = dict(meta=dict(title='', xlabel='', units=''), data=[])

		# Set the keys
		if researcher:
			results['meta']['keys'] = self.private_keys
			results['meta']['units'] = self.private_units
		else:
			results['meta']['keys'] = self.public_keys
			results['meta']['units'] = self.public_units

		# data should be returned as an array of dictionaries
		if data.count() != 0:
			results['meta']['title'] 	= "{} | {}, {}".format(self.sn, self.location, self.city)
			results['meta']['xlabel']	= "Datetime [ {} ]".format(self.timezone) if self.timezone else "Datetime [ UTC ]"
			results['meta']['ylabel'] 	= 'PM2.5 (ug/m3)'

			# Export the data
			results['data'] = [each._plotly(researcher=researcher) for each in data]

		return results

	def to_geojson_feature(self, pollutant=None):
		"""Load an instrument and return in geosjon format to display on
		the MapBox map.
		"""
		feature = self._to_geojson_feature(pollutant=pollutant)

		# get the most recent datapoint
		recent = self.most_recent_datapoint()

		# adjust the params to fit Orphan
		feature['properties']['unit'] = 'ug/m3'
		feature['properties']['value'] = recent.conc_hr
		feature['properties']['timestamp'] = recent.timestamp.isoformat()
		feature['properties']['flag'] = recent.flag

		return feature


class TREX(Instrument):
	__tablename__ 	= 'trex_instrument'
	__mapper_args__	= {'polymorphic_identity': 'trex'}

	id 				= db.Column(db.Integer, db.ForeignKey('instrument.id'), primary_key=True)
	results			= db.relationship('TrexData', backref='device',
						cascade='all, delete-orphan', lazy='dynamic')
	so2_model_id 	= db.Column(db.Integer, db.ForeignKey('model.id'))
	so2_model 		= db.relationship('Model', foreign_keys=[so2_model_id], uselist=False)

	cols_to_keep = ['so2', 'temp', 'rh', 'flag']

	public_keys = ['SO2', 'Temperature', 'Relative Humidity']
	public_units = ['ppb', 'degC', '%']

	private_keys = public_keys + ['SO2_WE', 'SO2_AE']
	private_units = public_units + ['mV', 'mV']

	params = ['so2']

	def __init__(self, **kwargs):
		super(TREX, self).__init__(discriminator='trex', **kwargs)

	@property
	def public_cols(self):
		return ['so2', 'temp', 'rh', 'flag', 'instr_sn']

	@property
	def private_cols(self):
		cols = [m.key for m in TrexData.__table__.columns]

		cols.remove('id')
		cols.remove('timestamp')

		return cols

	def evaluate(self, data):
		"""Evaluate the dictionary per the most up-to-date model of the parent
		Returns a dictionary.
		"""
		# Check to see if the parent has a model
		# If it does, evaluate and set data['so2'], else return the current dictionary
		if self.so2_model_id:
			model = self.so2_model.load_from_file()

			# Ensure the model has a `predict` method
			try:
				if hasattr(model, 'prepare'):
					values = model.prepare(data)
				else:
					values = [data['so2_we'], data['so2_ae'], data['temp'], data['rh']]
			except:
				sentry.captureException()

			# Evaluate the model
			try:
				data['so2'] = float(model.predict(values)[0])

				# Set the model id
				data['model_id'] = self.so2_model_id
			except TypeError:
				sentry.captureException()

				return data

		return data

	@staticmethod
	def create(data):
		instrument = TREX()

		instrument.from_dict(data)

		return instrument

	def _plotly(self, span='1d', researcher=False, **kwargs):
		"""Return data in a plotly-readable format"""
		t0 = calculate_start_timestamp(span)

		# Retrieve the data
		data = db.session.query(TrexData).filter(TrexData.instr_sn == self.sn,
					TrexData.timestamp >= t0).order_by(desc(TrexData.timestamp))

		# initialize results
		results = dict(meta=dict(title='', xlabel='', units=''), data=[])

		# Set the keys
		if researcher:
			results['meta']['keys'] = self.private_keys
			results['meta']['units'] = self.private_units
		else:
			results['meta']['keys'] = self.public_keys
			results['meta']['units'] = self.public_units

		# data should be returned as an array of dictionaries
		if data.count() != 0:
			results['meta']['title'] = "{} | {}, {}".format(self.sn, self.location, self.city)
			results['meta']['xlabel'] = "Datetime [ {} ]".format(self.timezone) if self.timezone else "Datetime [ UTC ]"

			# Export the data
			results['data'] = [each._plotly(researcher=researcher) for each in data]

		return results

	def to_geojson_feature(self, pollutant=None):
		"""Load an instrument and return in geosjon format to display on
		the MapBox map.
		"""
		feature = self._to_geojson_feature(pollutant=pollutant)

		# get the most recent datapoint
		recent = self.most_recent_datapoint()

		# adjust the params to fit Orphan
		feature['properties']['unit'] = 'ppb'
		feature['properties']['value'] = recent.so2
		feature['properties']['timestamp'] = recent.timestamp.isoformat()
		feature['properties']['flag'] = recent.flag

		return feature


class TrexPM(Instrument):
	__tablename__ = 'trex_pm'
	__mapper_args__ = {'polymorphic_identity': 'trex_pm'}

	id 			= db.Column(db.Integer, db.ForeignKey('instrument.id'), primary_key=True)
	results		= db.relationship('TrexPMData', backref='device',
						cascade='all, delete-orphan', lazy='dynamic')
	pm_model_id	= db.Column(db.Integer, db.ForeignKey('model.id'))
	pm_model 	= db.relationship('Model', foreign_keys=[pm_model_id], uselist=False)

	cols_to_keep = ['pm25', 'pm10', 'rh', 'temp', 'flag']

	public_keys = ['PM2.5', 'PM10', 'Temperature', 'Relative Humidity']
	public_units = ['ugm3', 'ugm3', 'degC', '%']

	private_keys = public_keys + ['PM1']
	private_units = public_units +['ugm3']

	params = ['pm25', 'pm10']

	def __init__(self, **kwargs):
		super(TrexPM, self).__init__(discriminator='trex_pm', **kwargs)

	@property
	def public_cols(self):
		return ['pm25', 'pm10', 'temp', 'rh', 'flag', 'instr_sn']

	@property
	def private_cols(self):
		cols = [m.key for m in TrexPMData.__table__.columns]

		cols.remove('timestamp')
		cols.remove('id')

		return cols

	def evaluate(self, data):
		return None

	@staticmethod
	def create(data):
		instrument = TrexPM()

		instrument.from_dict(data)

		return instrument

	def _plotly(self, span='1d', researcher=False, **kwargs):
		"""Return data in a plotly-readable format"""
		t0 = calculate_start_timestamp(span)

		# Retrieve the data
		data = db.session.query(TrexPMData).filter(TrexPMData.instr_sn == self.sn,
					TrexPMData.timestamp >= t0).order_by(desc(TrexPMData.timestamp))

		# initialize results
		results = dict(meta=dict(title='', xlabel='', units=''), data=[])

		# Set the keys
		if researcher:
			results['meta']['keys'] = self.private_keys
			results['meta']['units'] = self.private_units
		else:
			results['meta']['keys'] = self.public_keys
			results['meta']['units'] = self.public_units

		# data should be returned as an array of dictionaries
		if data.count() != 0:
			results['meta']['title'] = "{} | {}, {}".format(self.sn, self.location, self.city)
			results['meta']['xlabel'] = "Datetime [ {} ]".format(self.timezone) if self.timezone else "Datetime [ UTC ]"

			# Export the data
			results['data'] = [each._plotly(researcher=researcher) for each in data]

		return results

	def to_geojson_feature(self, pollutant=None):
		"""Load an instrument and return in geosjon format to display on
		the MapBox map.
		"""
		feature = self._to_geojson_feature(pollutant=pollutant)

		# get the most recent datapoint
		recent = self.most_recent_datapoint()

		feature['properties']['unit'] = 'ug/m3'

		if recent:
			if pollutant == 'pm25':
				value = recent.pm25
			else:
				value = recent.pm10

			# adjust the params to fit
			feature['properties']['value'] = value
			feature['properties']['timestamp'] = recent.timestamp.isoformat()
			feature['properties']['flag'] = recent.flag
		else:
			feature['properties']['value'] = None
			feature['properties']['timestamp'] = None
			feature['properties']['flag'] = None

		return feature




class Data(db.Model):
	__tablename__ = 'data'

	id 				= db.Column(db.Integer, primary_key=True)
	timestamp 		= db.Column(db.DateTime)
	value 			= db.Column(db.Float)
	parameter 		= db.Column(db.String(24), index=True)
	unit 			= db.Column(db.String(24))
	flag 			= db.Column(db.Integer)
	status 			= db.Column(db.Integer)
	instr_sn 		= db.Column(db.String(24), db.ForeignKey('instrument.sn', onupdate='CASCADE',
							ondelete='CASCADE'), index=True)
	model_id		= db.Column(db.Integer, db.ForeignKey('model.id', onupdate='CASCADE'), index=True)
	model 			= db.relationship('Model', foreign_keys=[model_id], uselist=False)

	@staticmethod
	def create(data):
		new = Data()

		new.from_dict(data)

		return new

	def from_dict(self, data, partial_update=False):
		for field in ['timestamp', 'value', 'instr_sn']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				if not partial_update:
					raise KeyError

		# all other optional fields
		for field in ['parameter', 'unit', 'flag', 'status', 'model_id']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				pass

	@staticmethod
	def from_webhook(data, sn):
		"""Return a dictionary of data after splitting"""
		data = data.split(',')

		result = dict()
		result['instr_sn'] = sn
		result['timestamp'] = dateutil.parser.parse(data[0])
		result['value'] = safe_cast(data[1])
		result['parameter'] = data[2]
		result['unit'] = data[3]
		result['flag'] = bool(data[4])

		return result

	def to_json(self, researcher=False):
		payload = {'data': [], 'meta': {}}

		payload = {
			'instrument': self.device.get_url(),
			'timestamp': self.timestamp.isoformat(),
			'timestamp_local': to_timezone(self.timestamp, self.device.timezone),
			'flag': self.flag,
			'id': self.id,
		}

		payload[self.parameter] = {
			'value': self.value,
			'unit': self.unit,
		}

		return payload

	def _plotly(self, **kwargs):
		"""Export each datapoint in a plotly-friendly format"""

		# shouldn't need the first part of this; for some reason, some data points
		# are being returned with no parent!
		if self.device and self.device.timezone:
			tz_local 	= pytz.timezone(self.device.timezone)
			ts 			= str(self.timestamp.replace(tzinfo=pytz.UTC).astimezone(tz_local).replace(tzinfo=None))
		else:
			ts = None

		output = {
			'timestamp': ts if ts else str(self.timestamp),
			'value': self.value,
			'parameter': self.parameter,
			'unit': self.unit,
			'flag': self.flag
			}

		return output

	def get_url(self):
		return url_for('api_1_0.get_datapoint_by_dev', sn=self.device.id, id=self.id, _external=True, _scheme='https')

	@staticmethod
	def fake(ts, sn):
		d = {
			'timestamp': ts,
			'instr_sn': sn,
			'value': random.random(),
			'parameter': 'o3',
			'unit': 'ppbv',
			'flag': random.choice([0, 1]),
			'status': 1,
			}

		return Data(**d)

	def update_parent(self):
		return self.device.update()

	def drop(self):
		db.session.delete(self)
		db.session.commit()

		return True

	def __repr__(self):
		return "Data {}: {}".format(self.id, self.parameter)


class MITData(db.Model):
	__tablename__ = 'mit_data'

	id 				= db.Column(db.Integer, primary_key=True)
	timestamp		= db.Column(db.DateTime)
	instr_sn 		= db.Column(db.String(24), db.ForeignKey('instrument.sn', onupdate='CASCADE',
							ondelete='CASCADE'), index=True)
	co_we			= db.Column(db.Float)
	co_ae 		 	= db.Column(db.Float)
	co				= db.Column(db.Float)
	ox_we			= db.Column(db.Float)
	ox_ae 		 	= db.Column(db.Float)
	o3				= db.Column(db.Float)
	so2_we			= db.Column(db.Float)
	so2_ae 		 	= db.Column(db.Float)
	so2				= db.Column(db.Float)
	nox_we			= db.Column(db.Float)
	nox_ae 		 	= db.Column(db.Float)
	nox				= db.Column(db.Float)
	bin0 			= db.Column(db.Float)
	bin1 			= db.Column(db.Float)
	bin2 			= db.Column(db.Float)
	bin3 			= db.Column(db.Float)
	bin4 			= db.Column(db.Float)
	bin5 			= db.Column(db.Float)
	bin6 			= db.Column(db.Float)
	bin7 			= db.Column(db.Float)
	bin8 			= db.Column(db.Float)
	bin9 			= db.Column(db.Float)
	bin10 			= db.Column(db.Float)
	bin11 			= db.Column(db.Float)
	bin12 			= db.Column(db.Float)
	bin13 			= db.Column(db.Float)
	bin14 			= db.Column(db.Float)
	bin15 			= db.Column(db.Float)
	bin1MToF 		= db.Column(db.Float)
	bin3MToF 		= db.Column(db.Float)
	bin5MToF 		= db.Column(db.Float)
	bin7MToF 		= db.Column(db.Float)
	pm1 			= db.Column(db.Float)
	pm25 			= db.Column(db.Float)
	pm10			= db.Column(db.Float)
	period 			= db.Column(db.Float)
	sfr 			= db.Column(db.Float)
	rh_i 			= db.Column(db.Float)
	temp_i 			= db.Column(db.Float)
	cycles 		 	= db.Column(db.Float)
	flag 			= db.Column(db.Integer)
	last_updated	= db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

	co_model_id		= db.Column(db.Integer, db.ForeignKey('model.id'), index=True)
	nox_model_id	= db.Column(db.Integer, db.ForeignKey('model.id'), index=True)
	so2_model_id	= db.Column(db.Integer, db.ForeignKey('model.id'), index=True)
	ox_model_id		= db.Column(db.Integer, db.ForeignKey('model.id'), index=True)
	pm_model_id		= db.Column(db.Integer, db.ForeignKey('model.id'), index=True)

	co_model 		= db.relationship('Model', foreign_keys=[co_model_id], uselist=False)
	nox_model 		= db.relationship('Model', foreign_keys=[nox_model_id], uselist=False)
	so2_model 		= db.relationship('Model', foreign_keys=[so2_model_id], uselist=False)
	ox_model 		= db.relationship('Model', foreign_keys=[ox_model_id], uselist=False)
	pm_model 		= db.relationship('Model', foreign_keys=[pm_model_id], uselist=False)

	@staticmethod
	def create(data):
		new = MITData()

		new.from_dict(data)

		return new

	def from_dict(self, data, partial_update=False):
		for field in ['timestamp', 'instr_sn']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				if not partial_update:
					raise KeyError

		# all other optional fields
		for field in ['co_we', 'co_ae', 'co', 'ox_we', 'ox_ae', 'o3', 'so2_we',
						'so2_ae', 'so2', 'nox_we', 'nox_ae', 'nox', 'bin0',
						'bin1', 'bin2', 'bin3', 'bin4', 'bin5', 'bin6', 'bin7',
						'bin8', 'bin9', 'bin10', 'bin11', 'bin12', 'bin13',
						'bin14', 'bin15', 'bin1MToF', 'bin3MToF', 'bin5MToF',
						'bin7MToF', 'pm1', 'pm25', 'pm10', 'period', 'sfr',
						'rh_i', 'temp_i', 'cycles', 'flag', 'co_model_id',
						'nox_model_id', 'so2_model_id', 'ox_model_id', 'pm_model_id']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				pass

	@staticmethod
	def from_webhook(data, sn):
		"""Return a dictionary of data after splitting"""
		data = data.split(',')

		mult = int(data[-1])
		if mult != 0.0:
			mult = 1./mult

		result = dict()
		result['instr_sn'] = sn
		result['timestamp'] = dateutil.parser.parse(data[0])
		result['cycles'] = safe_cast(data[1], func=int)
		result['flag'] = safe_cast(data[2], func=int)
		result['rh_i'] = safe_cast(data[3])
		result['temp_i'] = safe_cast(data[4])
		result['co_we'] = safe_cast(data[5])
		result['co_ae'] = safe_cast(data[6])
		result['nox_we'] = safe_cast(data[7])
		result['nox_ae'] = safe_cast(data[8])
		result['so2_we'] = safe_cast(data[9])
		result['so2_ae'] = safe_cast(data[10])
		result['ox_we'] = safe_cast(data[11])
		result['ox_ae'] = safe_cast(data[12])
		result['bin0'] = safe_cast(data[13], mult)
		result['bin1'] = safe_cast(data[14], mult)
		result['bin2'] = safe_cast(data[15], mult)
		result['bin3'] = safe_cast(data[16], mult)
		result['bin4'] = safe_cast(data[17], mult)
		result['bin5'] = safe_cast(data[18], mult)
		result['bin6'] = safe_cast(data[19], mult)
		result['bin7'] = safe_cast(data[20], mult)
		result['bin8'] = safe_cast(data[21], mult)
		result['bin9'] = safe_cast(data[22], mult)
		result['bin10'] = safe_cast(data[23], mult)
		result['bin11'] = safe_cast(data[24], mult)
		result['bin12'] = safe_cast(data[25], mult)
		result['bin13'] = safe_cast(data[26], mult)
		result['bin14'] = safe_cast(data[27], mult)
		result['bin15'] = safe_cast(data[28], mult)
		result['pm1'] = safe_cast(data[29], mult)
		result['pm25'] = safe_cast(data[30], mult)
		result['pm10'] = safe_cast(data[31], mult)
		result['period'] = safe_cast(data[32])
		result['bin1MToF'] = safe_cast(data[33])
		result['bin3MToF'] = safe_cast(data[34])
		result['bin5MToF'] = safe_cast(data[35])
		result['bin7MToF'] = safe_cast(data[36])
		result['sfr'] = safe_cast(data[37])

		return result

	@staticmethod
	def fake(ts, sn):
		d = {
			'timestamp': ts,
			'instr_sn': sn,
			'so2': random.random(),
			'so2_we': random.random(),
			'so2_ae': random.random(),
			'co': random.random(),
			'co_we': random.random(),
			'co_ae': random.random(),
			'o3': random.random(),
			'ox_we': random.random(),
			'ox_ae': random.random(),
			'nox': random.random(),
			'nox_we': random.random(),
			'nox_ae': random.random(),
			'bin0': random.random(),
			'bin1': random.random(),
			'bin2': random.random(),
			'bin3': random.random(),
			'bin4': random.random(),
			'bin5': random.random(),
			'bin6': random.random(),
			'bin7': random.random(),
			'bin8': random.random(),
			'bin9': random.random(),
			'bin10': random.random(),
			'bin11': random.random(),
			'bin12': random.random(),
			'bin13': random.random(),
			'bin14': random.random(),
			'bin15': random.random(),
			'pm1': random.random(),
			'pm25': random.random(),
			'pm10': random.random(),
			'temp_i': random.random(),
			'rh_i': random.random(),
			}

		return MITData(**d)

	def to_json(self, researcher=False, **kwargs):
		"""Return a dictionary of values.
		"""
		payload = {
			'timestamp': self.timestamp.isoformat(),
			'timestamp_local': to_timezone(self.timestamp, self.device.timezone),
			'instrument': self.device.get_url(),
			'id': self.id,
			'flag': self.flag,
		}

		payload['co'] = {'value': self.co, 'unit': 'ppbv'}
		payload['o3'] = {'value': self.o3, 'unit': 'ppbv'}
		payload['nox'] = {'value': self.nox, 'unit': 'ppbv'}
		payload['so2'] = {'value': self.so2, 'unit': 'ppbv'}
		payload['pm1'] = {'value': self.pm1, 'unit': 'ug/m3'}
		payload['pm25'] = {'value': self.pm25, 'unit': 'ug/m3'}
		payload['pm10'] = {'value': self.pm10, 'unit': 'ug/m3'}
		payload['rh'] = {'value': self.rh_i, 'unit': '%'}
		payload['temp'] = {'value': self.temp_i, 'unit': 'degC'}

		if researcher is True:
			payload['co']['we'] = {'value': self.co_we, 'unit': 'mV'}
			payload['co']['ae'] = {'value': self.co_ae, 'unit': 'mV'}
			payload['o3']['we'] = {'value': self.ox_we, 'unit': 'mV'}
			payload['o3']['ae'] = {'value': self.ox_ae, 'unit': 'mV'}
			payload['nox']['we'] = {'value': self.nox_we, 'unit': 'mV'}
			payload['nox']['ae'] = {'value': self.nox_ae, 'unit': 'mV'}
			payload['so2']['we'] = {'value': self.so2_we, 'unit': 'mV'}
			payload['so2']['ae'] = {'value': self.so2_ae, 'unit': 'mV'}

			payload['opc'] = {
				'bin0': self.bin0,
				'bin1': self.bin1,
				'bin2': self.bin2,
				'bin3': self.bin3,
				'bin4': self.bin4,
				'bin5': self.bin5,
				'bin6': self.bin6,
				'bin7': self.bin7,
				'bin8': self.bin8,
				'bin9': self.bin9,
				'bin10': self.bin10,
				'bin11': self.bin11,
				'bin12': self.bin12,
				'bin13': self.bin13,
				'bin14': self.bin14,
				'bin15': self.bin15,
				'bin1MToF': self.bin1MToF,
				'bin3MToF': self.bin3MToF,
				'bin5MToF': self.bin5MToF,
				'bin7MToF': self.bin7MToF,
				'period': self.period,
				'sfr': self.sfr,
				'cycles': self.cycles,
				'last_updated': self.last_updated.isoformat()
			}

		return payload

	def _plotly(self, researcher=False, **kwargs):
		res = dict()

		res['timestamp'] = self.timestamp.isoformat()
		res['CO'] = self.co
		res['O3'] = self.o3
		res['NOx'] = self.nox
		res['SO2'] = self.so2
		res['PM1'] = self.pm1
		res['PM25'] = self.pm25
		res['PM10'] = self.pm10
		res['RH'] = self.rh_i
		res['Temperature'] = self.temp_i

		if self.device.timezone:
			res['timestamp'] = str(to_timezone(self.timestamp,
						self.device.timezone, replace=True, isoformat=False))

		if researcher:
			res['CO_WE'] = self.co_we
			res['O3_WE'] = self.ox_we
			res['SO2_WE'] = self.so2_we
			res['NOX_WE'] = self.nox_we

		return res

	def get_url(self):
		return url_for('api_1_0.get_datapoint_by_dev', sn=self.instr_sn, id=self.id, _external=True, _scheme='https')

	def update_parent(self):
		self.device.update()

		return

	def drop(self):
		db.session.delete(self)
		db.session.commit()

		return True

	def __repr__(self):
		return "Timestamp: {}".format(self.timestamp.isoformat())


class EBamData(db.Model):
	__tablename__ 	= 'ebam_data'

	id 				= db.Column(db.Integer, primary_key=True, autoincrement=True)
	timestamp		= db.Column(db.DateTime, nullable=False)
	conc_rt 		= db.Column(db.Float, nullable=False)
	conc_hr			= db.Column(db.Float, nullable=False)
	flowrate 		= db.Column(db.Float)
	wind_speed 		= db.Column(db.Float)
	wind_dir 		= db.Column(db.Float)
	ambient_temp	= db.Column(db.Float)
	rh_external		= db.Column(db.Float)
	rh_internal		= db.Column(db.Float)
	bv_c			= db.Column(db.Float)
	ft_c			= db.Column(db.Float)
	flag 			= db.Column(db.Integer)
	instr_sn		= db.Column(db.String(24), db.ForeignKey('instrument.sn', onupdate='CASCADE',
								ondelete='CASCADE'), index=True)
	model_id		= db.Column(db.Integer, db.ForeignKey('model.id', onupdate='CASCADE'), index=True)
	model 			= db.relationship('Model', foreign_keys=[model_id], uselist=False)

	@staticmethod
	def create(data):
		new = EBamData()

		new.from_dict(data)

		return new

	def from_dict(self, data, partial_update=False):
		# Do some weird shit to get around shitty keys
		replacement_keys = [('flow', 'flowrate'), ('ws', 'windspeed'),
			('wd', 'wind_dir'), ('at', 'ambient_temp'), ('rhx', 'rh_external'),
			('rhi', 'rh_internal'), ('alarm', 'flag')]

		for old, new in replacement_keys:
			if old in data.keys():
				data[new] = data[old]

				data.pop(old)

		for field in ['timestamp', 'conc_rt', 'conc_hr', 'instr_sn']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				if not partial_update:
					raise KeyError

		# all other optional fields
		for field in ['flowate', 'wind_speed', 'wind_dir', 'ambient_temp',
					'rh_external', 'rh_interal', 'bv_c', 'ft_c', 'flag']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				pass

	def to_json(self, researcher=False):
		# Set up the dictionary to return
		payload = {
			'timestamp': self.timestamp.isoformat(),
			'timestamp_local': to_timezone(self.timestamp, self.device.timezone),
			'flag': self.flag,
			'id': self.id,
			'instrument': self.device.get_url(),
		}

		payload['pm25'] = {'value': self.conc_hr, 'unit': 'ug/m3'}
		payload['rh'] = {'value': self.rh_external, 'unit': '%'}
		payload['temp'] = {'value': self.ambient_temp, 'unit': 'degC'}

		if researcher is True:
			payload['pm25_10min'] = {'value': self.conc_rt, 'unit': 'ug/m3'}
			payload['flowrate'] = {'value': self.flowrate, 'unit': 'LPM'}
			payload['wind_speed'] = {'value': self.wind_speed, 'unit': ''}
			payload['wind_dir'] = {'value': self.wind_dir, 'unit': ''}

		return payload

	def get_url(self):
		return url_for('api_1_0.get_datapoint_by_dev', sn=self.instr_sn, id=self.id, _external=True, _scheme='https')

	def _plotly(self, researcher=False, **kwargs):
		if self.device.timezone:
			tz_local = pytz.timezone(self.device.timezone)
			#ts = str(self.timestamp.replace(tzinfo=pytz.UTC).astimezone(tz_local).replace(tzinfo=None))
			# Assume timezone isn't an issue
			ts = None
		else:
			ts = None

		output = {
			"timestamp": ts if ts else str(self.timestamp),
			'Conc. (10min)': self.conc_rt,
			'Conc. (1hr)': self.conc_hr,
			'Flowrate': self.flowrate,
			'Wind Speed': self.wind_speed,
			'Wind Dir.': self.wind_dir,
			'Ambient Temp. (C)': self.ambient_temp,
			"Flag": self.flag,
			}

		return output

	def update_parent(self):
		return self.device.update()

	def drop(self):
		db.session.delete(self)
		db.session.commit()

		return True

	@staticmethod
	def fake(ts, sn):
		d = {
			'timestamp': ts,
			'conc_rt': random.random(),
			'conc_hr': random.random(),
			'instr_sn': sn,
			'flow': random.random(),
			'ws': random.random(),
			'wd': random.random(),
			'at': random.random(),
			'rhx': random.random(),
			'rhi': random.random()
			}

		return EBamData.create(d)

	def __repr__(self):
		return "{}: {} ug/m3".format(self.timestamp.isoformat(), self.conc_hr)


class TrexData(db.Model):
	__tablename__ = 'trex_data'

	id 				= db.Column(db.Integer, primary_key=True, autoincrement=True)
	timestamp		= db.Column(db.DateTime, nullable=False)
	so2 			= db.Column(db.Float)
	so2_we 			= db.Column(db.Float)
	so2_ae 			= db.Column(db.Float)
	temp			= db.Column(db.Float)
	rh				= db.Column(db.Float)
	flag            = db.Column(db.Integer)
	instr_sn		= db.Column(db.String(24), db.ForeignKey('instrument.sn',
							onupdate='CASCADE', ondelete='CASCADE'), index=True)
	model_id		= db.Column(db.Integer, db.ForeignKey('model.id', onupdate='CASCADE'), index=True)
	model 			= db.relationship('Model', foreign_keys=[model_id], uselist=False)

	@staticmethod
	def create(data):
		new = TrexData()

		new.from_dict(data)

		return new

	def from_dict(self, data, partial_update=False):
		for field in ['timestamp', 'instr_sn']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				if not partial_update:
					raise KeyError

		# all other optional fields
		for field in ['so2', 'so2_we', 'so2_ae', 'temp', 'rh', 'flag', 'model_id']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				pass

	@staticmethod
	def from_webhook(data, sn):
		"""Return a dictionary of data after splitting"""
		data = data.split(',')

		result = dict()
		result['instr_sn'] = sn
		result['timestamp'] = dateutil.parser.parse(data[0])
		result['so2_we'] = safe_cast(data[1])
		result['so2_ae'] = safe_cast(data[2])
		result['rh'] = safe_cast(data[3])
		result['temp'] = safe_cast(data[4])

		try:
			result['flag'] = bool(data[5])
		except: pass

		return result

	def to_json(self, researcher=False):
		payload = {
			'timestamp': self.timestamp.isoformat(),
			'timestamp_local': to_timezone(self.timestamp, self.device.timezone),
			'instrument': self.device.get_url(),
			'id': self.id,
			'flag': self.flag,
		}

		payload['so2'] = {'value': self.so2, 'unit': 'ppbv'}
		payload['rh'] = {'value': self.rh, 'unit': '%'}
		payload['temp'] = {'value': self.temp, 'unit': 'degC'}

		if researcher:
			payload['so2']['we'] = {'value': self.so2_we, 'unit': 'mV'}
			payload['so2']['ae'] = {'value': self.so2_ae, 'unit': 'mV'}

		return payload

	def _plotly(self, researcher=False):
		if self.device.timezone:
			tz_local = pytz.timezone(self.device.timezone)
			ts = str(self.timestamp.replace(tzinfo=pytz.UTC).astimezone(tz_local).replace(tzinfo=None))
		else:
			ts = None

		output = {
			'timestamp': ts if ts else str(self.timestamp),
			'SO2': self.so2,
			'Temperature': self.temp,
			'Relative Humidity': self.rh
			}

		# If the user can view this, add in SO2WE and SO2AE
		if researcher:
			output['SO2_WE'] = self.so2_we
			output['SO2_AE'] = self.so2_ae

		return output

	def get_url(self):
		return url_for('api_1_0.get_datapoint_by_dev', sn=self.instr_sn, id=self.id, _external=True, _scheme='https')

	def update_parent(self):
		return self.device.update()

	@staticmethod
	def fake(ts, sn):
		d = {
			'timestamp': ts,
			'so2': random.random(),
			'so2_we': random.random(),
			'so2_ae': random.random(),
			'instr_sn': sn,
			'temp': random.random(),
			'rh': random.random(),
			'flag': 0
			}

		return TrexData.create(d)

	def drop(self):
		db.session.delete(self)
		db.session.commit()

		return True

	def __repr__(self):
		return "TREX: {}, {:.2f}, {:.2f}, {:.1f}, {:.1f}, {}".format(self.timestamp.isoformat(), self.so2_we, self.so2_ae, self.temp, self.rh, self.flag)


class TrexPMData(db.Model):
	__tablename__ = 'trex_pm_data'

	id 				= db.Column(db.Integer, primary_key=True, autoincrement=True)
	timestamp		= db.Column(db.DateTime, nullable=False)
	pm1 			= db.Column(db.Float)
	pm25			= db.Column(db.Float)
	pm10 			= db.Column(db.Float)
	bin0 			= db.Column(db.Float)
	bin1 			= db.Column(db.Float)
	bin2 			= db.Column(db.Float)
	bin3 			= db.Column(db.Float)
	bin4 			= db.Column(db.Float)
	bin5 			= db.Column(db.Float)
	temp			= db.Column(db.Float)
	rh				= db.Column(db.Float)
	flag            = db.Column(db.Integer)
	instr_sn		= db.Column(db.String(24), db.ForeignKey('instrument.sn',
							onupdate='CASCADE', ondelete='CASCADE'), index=True)
	model_id		= db.Column(db.Integer, db.ForeignKey('model.id', onupdate='CASCADE'), index=True)
	model 			= db.relationship('Model', foreign_keys=[model_id], uselist=False)

	@staticmethod
	def create(data):
		new = TrexPMData()

		new.from_dict(data)

		return new

	def from_dict(self, data, partial_update=False):
		for field in ['timestamp', 'instr_sn']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				if not partial_update:
					raise KeyError

		# all other optional fields
		for field in ['pm1', 'pm25', 'pm10', 'bin0', 'bin1', 'bin2', 'bin3', 'bin4', 'bin5', 'temp', 'rh', 'flag', 'model_id']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				pass

	@staticmethod
	def from_webhook(data, sn):
		"""Return a dictionary of data after splitting"""
		data = data.split(',')

		result = dict()
		result['instr_sn'] = sn
		result['timestamp'] = dateutil.parser.parse(data[0])
		result['rh'] = safe_cast(data[1])
		result['temp'] = safe_cast(data[2])
		result['pm1'] = safe_cast(data[3])
		result['pm25'] = safe_cast(data[4])
		result['pm10'] = safe_cast(data[5])
		result['bin0'] = safe_cast(data[6])
		result['bin1'] = safe_cast(data[7])
		result['bin2'] = safe_cast(data[8])
		result['bin3'] = safe_cast(data[9])
		result['bin4'] = safe_cast(data[10])
		result['bin5'] = safe_cast(data[11])

		try:
			result['flag'] = bool(data[12])
		except: pass

		return result

	def to_json(self, researcher=False):
		payload = {
			'timestamp': self.timestamp.isoformat(),
			'timestamp_local': to_timezone(self.timestamp, self.device.timezone),
			'instrument': self.device.get_url(),
			'id': self.id,
			'flag': self.flag,
		}

		payload['pm25'] = {'value': self.pm25, 'unit': 'ug/m3'}
		payload['pm10'] = {'value': self.pm10, 'unit': 'ug/m3'}
		payload['rh'] = {'value': self.rh, 'unit': '%'}
		payload['temp'] = {'value': self.temp, 'unit': 'degC'}

		if researcher:
			payload['opc'] = {
				'bin0': self.bin0,
				'bin1': self.bin1,
				'bin2': self.bin2,
				'bin3': self.bin3,
				'bin4': self.bin4,
				'bin5': self.bin5
			}

			payload['pm1'] = {'value': self.pm1, 'unit': 'ug/m3'}

		return payload

	def _plotly(self, researcher=False):
		if self.device.timezone:
			tz_local = pytz.timezone(self.device.timezone)
			ts = str(self.timestamp.replace(tzinfo=pytz.UTC).astimezone(tz_local).replace(tzinfo=None))
		else:
			ts = None

		output = {
			'timestamp': ts if ts else str(self.timestamp),
			'PM2.5': self.pm25,
			'PM10': self.pm10,
			'Temperature': self.temp,
			'Relative Humidity': self.rh
			}

		# If the user can view this, add in SO2WE and SO2AE
		if researcher:
			output['PM1'] = self.pm1

		return output

	def get_url(self):
		return url_for('api_1_0.get_datapoint_by_dev', sn=self.instr_sn, id=self.id, _external=True, _scheme='https')

	def update_parent(self):
		return self.device.update()

	@staticmethod
	def fake(ts, sn):
		d = {
			'timestamp': ts,
			'pm1': random.random(),
			'pm25': random.random(),
			'pm10': random.random(),
			'bin0': random.random(),
			'bin1': random.random(),
			'bin2': random.random(),
			'bin3': random.random(),
			'bin4': random.random(),
			'bin5': random.random(),
			'instr_sn': sn,
			'temp': random.random(),
			'rh': random.random(),
			'flag': 0
			}

		return TrexPMData.create(d)

	def drop(self):
		db.session.delete(self)
		db.session.commit()

		return True

	def __repr__(self):
		return "TrexPM: {}, {:.2f}, {:.2f}, {:.2f}, {}".format(self.timestamp.isoformat(), self.pm1, self.pm25, self.pm10, self.flag)


########## OTHER THINGS ############
class Model(db.Model):
	__tablename__ = 'model'

	id 				= db.Column(db.Integer, primary_key=True, autoincrement=True)
	created 		= db.Column(db.DateTime, default=datetime.utcnow)
	last_updated 	= db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
	filename		= db.Column(db.String(200), unique=True)
	label 			= db.Column(db.String(100), unique=True)
	description 	= db.Column(db.Text)
	rmse 			= db.Column(db.Float)
	mae 			= db.Column(db.Float)
	r2				= db.Column(db.Float)
	instr_id		= db.Column(db.Integer, index=True)

	def drop(self):
		db.session.delete(self)
		db.session.commit()

		return True

	@property
	def parent(self):
		"""Return the parent Instrument instance"""
		if not self.instr_id:
			return None

		return Instrument.query.get(self.instr_id)

	def load_from_file(self):
		"""Load a model from file using joblib and return
		"""
		return joblib.load(os.path.join(current_app.config['MODELS_DIR'], self.filename))

	def __repr__(self):
		return self.label


class Log(db.Model):
	__tablename__ = 'log'

	id 				= db.Column(db.Integer, primary_key=True)
	opened 			= db.Column(db.DateTime, default=datetime.utcnow)
	closed 			= db.Column(db.DateTime)
	message 		= db.Column(db.String(128))
	addressed 		= db.Column(db.Boolean, default=False)
	level 			= db.Column(db.String(12), index=True, default='INFO')
	instr_sn 		= db.Column(db.String(24), db.ForeignKey('instrument.sn'), index=True)

	@staticmethod
	def create(data):
		log = Log()

		log.from_dict(data)

		return log

	def from_dict(self, data, partial_update=False):
		for field in ['instr_sn']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				if not partial_update:
					raise KeyError

		# all other optional fields
		for field in ['closed', 'message', 'addressed', 'level']:
			try:
				setattr(self, field, data[field])
			except KeyError:
				pass

	def get_url(self):
		return url_for('api_1_0.get_log', id=self.id, _external=True, _scheme='https')

	def to_json(self):
		return {
			'url': self.get_url(),
			'opened': self.opened.isoformat(),
			'closed': self.closed.isoformat() if self.closed else None,
			'instrument': self.device.sn,
			'message': self.message,
			'level': self.level,
			'addressed': self.addressed
			}

	def drop(self):
		db.session.delete(self)
		db.session.commit()

		return True

	def close(self):
		self.addressed 	= True
		self.closed 	= datetime.utcnow()

		db.session.commit()

		return True

	def __repr__(self):
		return "{} {} {}".format(self.opened, self.level, self.message)
