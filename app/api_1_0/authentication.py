from .errors import forbidden, unauthorized, bad_request
from . import api_1_0
from .decorators import json
from ..models import User, Credentials, Instrument

from functools import wraps
from flask import request
import flask_sqlalchemy

def check_auth(apikey):
    ''' If the API key exists, return True '''
    if Credentials.query.filter_by(key=apikey).count() == 0:
        return False
    else:
        return True

def can_write(apikey):
    credentials = Credentials.query.filter_by(key=apikey).first()
    if credentials is None:
        return False

    return credentials.can_write

def can_drop(apikey):
    credentials = Credentials.query.filter_by(key=apikey).first()
    if credentials is None:
        return False

    return credentials.can_drop

def requires_credentials(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization

        if isinstance(auth.username, bytes):
            auth.username = auth.username.decode('utf-8')

        if not auth or not check_auth(auth.username):
            return unauthorized("Invalid credentials")
        return f(*args, **kwargs)

    return decorated

def requires_write_access(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization

        if isinstance(auth.username, bytes):
            auth.username = auth.username.decode('utf-8')

        if not auth or not can_write(auth.username):
            return unauthorized("You do not have write access")
        return f(*args, **kwargs)

    return decorated

def requires_drop_access(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization

        if isinstance(auth.username, bytes):
            auth.username = auth.username.decode('utf-8')

        if not auth or not can_drop(auth.username):
            return unauthorized("You do not have write access")
        return f(*args, **kwargs)

    return decorated

def requires_viewing_privileges(f):
    """Can someone with API key X view device with SN=SN?
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        sn = kwargs.get('sn', None)
        auth = request.authorization

        if isinstance(auth.username, bytes):
            auth.username = auth.username.decode('utf-8')

        # Get the credentials
        key = Credentials.query.filter_by(key=auth.username).first()

        device = Instrument.query.filter_by(sn=sn).first()

        # Make sure the key exists
        if not key or not key.user_id:
            return bad_request("Invalid API key")

        # Make sure the device exists
        if not device:
            return bad_request("No device exists with this serial number.")

        # Check to see if the user can view the device
        if not key.User.canview(device):
            return unauthorized("This API does not have permisssions to view this device.")

        return f(*args, **kwargs)
    return decorated

def requires_research_privileges(f):
    """Can someone with API key X view research data?
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        sn = kwargs.get('sn', None)
        auth = request.authorization

        if isinstance(auth.username, bytes):
            auth.username = auth.username.decode('utf-8')

        # Get the credentials
        key = Credentials.query.filter_by(key=auth.username).first()

        # Make sure the key exists
        if not key or not key.user_id:
            return bad_request("Invalid API key")

        # Check to see if the user can view the device
        if not key.User.can_view_research_data:
            return unauthorized("This API does not have permisssions to view research level data.")

        return f(*args, **kwargs)
    return decorated

def filter_on_instrument_permissions(model):
    """Filter the collection based on the users/API key's permissions.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            query = f(*args, **kwargs)

            auth = request.authorization

            if isinstance(auth.username, bytes):
                auth.username = auth.username.decode('utf-8')

            # Get authorization
            key = Credentials.query.filter_by(key=auth.username).first()
            if key is None:
                return unauthorized("Invalid credentials")

            user = key.User
            if user is None:
                return unauthorized("Invalid credentials")

            # Make sure the user can view the Instrument
            # This should return all devices the user can view, not just the ones it owns!
            query = user.following

            # do some magic
            return query
        return wrapped
    return decorator

@api_1_0.before_request
def before_request():
    pass
