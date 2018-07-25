from functools import wraps
from flask import abort, request, url_for, redirect
from flask_login import current_user
from .models import Permission, Credentials

def permission_required(permission):
	def decorator(f):
		@wraps(f)
		def decorated_function(*args, **kwargs):
			if not current_user.can(permission):
				abort(403)
			return f(*args, **kwargs)
		return decorated_function
	return decorator

def admin_required(f):
	return permission_required(Permission.ADMINISTER)(f)

def superuser_required(f):
	return permission_required(Permission.DELETE)(f)

def api_write_access_required(f):
	return permission_required(Permission.API_WRITE)(f)

def confirmation_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if not current_user.confirmed:
			return redirect( url_for('main.unconfirmed') )
		return f(*args, **kwargs)
	return decorated_function
