"""Handles all API calls for posting, putting, and getting authentication requests"""
from flask  import request, abort, url_for, current_app
from .. import db
from . import api_1_0
from .authentication import requires_credentials, requires_write_access
from .decorators import json

@api_1_0.route('/auth/', methods=['GET'])
@requires_credentials
@json
def check_auth():
    """Check the users credentials
    """
    return {"Authentication Check": "All good!"}, 200
